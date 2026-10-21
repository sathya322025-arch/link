/**
 * WebRTC Connection and Signaling Manager
 * Handles RTCPeerConnection lifecycle, ICE exchange, DataChannel, and media tracks.
 */

class WebRTCManager {
  constructor({ role, sessionCode, iceServers, onRemoteStream, onDataMessage, onConnectionStateChange }) {
    this.role = role; // 'admin' or 'client'
    this.sessionCode = sessionCode;
    this.iceServers = iceServers || [{ urls: ["stun:stun.l.google.com:19302"] }];
    this.onRemoteStream = onRemoteStream;
    this.onDataMessage = onDataMessage;
    this.onConnectionStateChange = onConnectionStateChange;

    this.peerConnection = null;
    this.dataChannel = null;
    this.ws = null;
    this.localStream = null;
    this.candidateQueue = [];
    this.statsInterval = null;
  }

  connectSignaling(wsUrl) {
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(`${wsUrl}?role=${this.role}`);

      this.ws.onopen = () => {
        console.log(`[Signaling] WebSocket connected as ${this.role}`);
        this.initPeerConnection();
        resolve();
      };

      this.ws.onerror = (err) => {
        console.error("[Signaling] WebSocket error:", err);
        reject(err);
      };

      this.ws.onmessage = async (event) => {
        const msg = JSON.parse(event.data);
        await this.handleSignalingMessage(msg);
      };

      this.ws.onclose = () => {
        console.warn("[Signaling] WebSocket closed");
        if (this.onConnectionStateChange) {
          this.onConnectionStateChange("disconnected");
        }
      };
    });
  }

  initPeerConnection() {
    const config = {
      iceServers: this.iceServers,
      iceTransportPolicy: "all",
      bundlePolicy: "max-bundle",
      rtcpMuxPolicy: "require"
    };

    this.peerConnection = new RTCPeerConnection(config);

    // ICE Candidate Generation
    this.peerConnection.onicecandidate = (event) => {
      if (event.candidate) {
        this.sendSignal({
          type: "ice-candidate",
          candidate: event.candidate
        });
      }
    };

    // Connection State Changes
    this.peerConnection.onconnectionstatechange = () => {
      const state = this.peerConnection.connectionState;
      console.log(`[WebRTC] Connection state: ${state}`);
      if (this.onConnectionStateChange) {
        this.onConnectionStateChange(state);
      }
    };

    // Remote Track Handler
    this.peerConnection.ontrack = (event) => {
      console.log("[WebRTC] Remote track received:", event.track.kind);
      if (this.onRemoteStream && event.streams[0]) {
        this.onRemoteStream(event.streams[0]);
      }
    };

    // Data Channel Setup
    if (this.role === "admin") {
      this.dataChannel = this.peerConnection.createDataChannel("support-control", { ordered: true });
      this.setupDataChannelEvents(this.dataChannel);
    } else {
      this.peerConnection.ondatachannel = (event) => {
        this.dataChannel = event.channel;
        this.setupDataChannelEvents(this.dataChannel);
      };
    }
  }

  setupDataChannelEvents(dc) {
    dc.onopen = () => console.log("[DataChannel] Channel opened");
    dc.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (this.onDataMessage) this.onDataMessage(payload);
      } catch (err) {
        console.error("[DataChannel] Error parsing message:", err);
      }
    };
    dc.onclose = () => console.log("[DataChannel] Channel closed");
  }

  sendData(payload) {
    if (this.dataChannel && this.dataChannel.readyState === "open") {
      this.dataChannel.send(JSON.stringify(payload));
    }
  }

  sendSignal(data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  async attachLocalScreen(stream) {
    this.localStream = stream;
    stream.getTracks().forEach((track) => {
      this.peerConnection.addTrack(track, stream);
    });

    // Client initiates the offer upon adding the screen
    const offer = await this.peerConnection.createOffer();
    await this.peerConnection.setLocalDescription(offer);

    this.sendSignal({
      type: "offer",
      sdp: this.peerConnection.localDescription
    });
  }

  async handleSignalingMessage(msg) {
    switch (msg.type) {
      case "offer":
        await this.peerConnection.setRemoteDescription(new RTCSessionDescription(msg.sdp));
        this.processCandidateQueue();
        const answer = await this.peerConnection.createAnswer();
        await this.peerConnection.setLocalDescription(answer);
        this.sendSignal({
          type: "answer",
          sdp: this.peerConnection.localDescription
        });
        break;

      case "answer":
        await this.peerConnection.setRemoteDescription(new RTCSessionDescription(msg.sdp));
        this.processCandidateQueue();
        break;

      case "ice-candidate":
        const candidate = new RTCIceCandidate(msg.candidate);
        if (this.peerConnection.remoteDescription) {
          await this.peerConnection.addIceCandidate(candidate);
        } else {
          this.candidateQueue.push(candidate);
        }
        break;

      case "peer_joined":
        console.log(`[Signaling] Peer joined: ${msg.role}`);
        break;

      case "session_paused":
        if (this.onConnectionStateChange) this.onConnectionStateChange("paused");
        break;

      case "session_resumed":
        if (this.onConnectionStateChange) this.onConnectionStateChange("active");
        break;

      case "session_terminated":
        if (this.onConnectionStateChange) this.onConnectionStateChange("ended");
        this.close();
        break;
    }
  }

  async processCandidateQueue() {
    while (this.candidateQueue.length > 0) {
      const candidate = this.candidateQueue.shift();
      try {
        await this.peerConnection.addIceCandidate(candidate);
      } catch (e) {
        console.error("[WebRTC] Error adding buffered ICE candidate:", e);
      }
    }
  }

  startStatsMonitor(callback) {
    this.statsInterval = setInterval(async () => {
      if (!this.peerConnection) return;
      const stats = await this.peerConnection.getStats();
      let activeStats = { fps: 0, bitrateKbps: 0, rttMs: 0, packetsLost: 0 };

      stats.forEach((report) => {
        if (report.type === "inbound-rtp" && report.kind === "video") {
          activeStats.fps = report.framesPerSecond || 0;
          activeStats.packetsLost = report.packetsLost || 0;
        }
        if (report.type === "candidate-pair" && report.state === "succeeded") {
          activeStats.rttMs = Math.round((report.currentRoundTripTime || 0) * 1000);
        }
      });
      callback(activeStats);
    }, 1500);
  }

  close() {
    if (this.statsInterval) clearInterval(this.statsInterval);
    if (this.localStream) {
      this.localStream.getTracks().forEach((track) => track.stop());
    }
    if (this.dataChannel) this.dataChannel.close();
    if (this.peerConnection) this.peerConnection.close();
    if (this.ws && this.ws.readyState === WebSocket.OPEN) this.ws.close();
  }
}

window.WebRTCManager = WebRTCManager;

