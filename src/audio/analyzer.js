const DEFAULT_OPTIONS = {
  fftSize: 2048,
  smoothingTimeConstant: 0.82,
  minDecibels: -90,
  maxDecibels: -10,
};

export class AudioAnalyzer {
  constructor(options = {}) {
    this.options = { ...DEFAULT_OPTIONS, ...options };
    this.audioContext = null;
    this.analyser = null;
    this.source = null;
    this.stream = null;
    this.frequencyData = null;
    this.timeDomainData = null;
    this.level = 0;
  }

  async connectStream(stream) {
    this.disconnect();

    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    this.audioContext = new AudioContextClass();
    this.stream = stream;
    this.source = this.audioContext.createMediaStreamSource(stream);
    this.analyser = this.audioContext.createAnalyser();
    this.analyser.fftSize = this.options.fftSize;
    this.analyser.smoothingTimeConstant = this.options.smoothingTimeConstant;
    this.analyser.minDecibels = this.options.minDecibels;
    this.analyser.maxDecibels = this.options.maxDecibels;

    this.frequencyData = new Uint8Array(this.analyser.frequencyBinCount);
    this.timeDomainData = new Uint8Array(this.analyser.fftSize);

    this.source.connect(this.analyser);

    if (this.audioContext.state === 'suspended') {
      await this.audioContext.resume();
    }
  }

  setFftSize(fftSize) {
    this.options.fftSize = fftSize;

    if (!this.analyser) {
      return;
    }

    this.analyser.fftSize = fftSize;
    this.frequencyData = new Uint8Array(this.analyser.frequencyBinCount);
    this.timeDomainData = new Uint8Array(this.analyser.fftSize);
  }

  setSmoothing(smoothingTimeConstant) {
    this.options.smoothingTimeConstant = smoothingTimeConstant;

    if (this.analyser) {
      this.analyser.smoothingTimeConstant = smoothingTimeConstant;
    }
  }

  getFrame() {
    if (!this.analyser || !this.frequencyData || !this.timeDomainData) {
      return null;
    }

    this.analyser.getByteFrequencyData(this.frequencyData);
    this.analyser.getByteTimeDomainData(this.timeDomainData);

    let sumSquares = 0;

    for (let index = 0; index < this.timeDomainData.length; index += 1) {
      const normalized = (this.timeDomainData[index] - 128) / 128;
      sumSquares += normalized * normalized;
    }

    this.level = Math.sqrt(sumSquares / this.timeDomainData.length);

    return {
      frequencyData: this.frequencyData,
      timeDomainData: this.timeDomainData,
      level: this.level,
      sampleRate: this.audioContext?.sampleRate ?? 44100,
      fftSize: this.analyser.fftSize,
      binCount: this.analyser.frequencyBinCount,
    };
  }

  disconnect() {
    if (this.source) {
      this.source.disconnect();
    }

    if (this.stream) {
      this.stream.getTracks().forEach((track) => track.stop());
    }

    if (this.audioContext) {
      this.audioContext.close();
    }

    this.audioContext = null;
    this.analyser = null;
    this.source = null;
    this.stream = null;
    this.frequencyData = null;
    this.timeDomainData = null;
    this.level = 0;
  }
}
