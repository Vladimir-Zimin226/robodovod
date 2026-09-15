export class AudioEngine {
  constructor() {
    this.context = null; this.master = null; this.muted = false;
    this.beepTimer = 0; this.stepTimer = 0; this.sceneTimer = 4;
    this.template = 'warehouse'; this.noiseBuffer = null;
    this.ambientNodes = []; this.robotStates = new Map();
  }

  start() {
    if (this.context) { this.context.resume?.(); return; }
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (!AudioContext) return;
    this.context = new AudioContext();
    this.master = this.context.createGain();
    this.master.gain.value = this.muted ? 0 : .28;
    this.master.connect(this.context.destination);
    this.noiseBuffer = this.createNoiseBuffer();
    this.createRobotMotor();
    this.setScene(this.template);
  }

  setScene(template) {
    this.template = template || 'warehouse';
    this.robotStates.clear();
    if (!this.context) return;
    this.ambientNodes.forEach(node => { try { node.stop(); } catch { /* already stopped */ } });
    this.ambientNodes = [];
    const profiles = {
      warehouse: [[43, 'sine', .055], [86, 'triangle', .018], [138, 'sine', .008]],
      airport: [[52, 'sine', .035], [104, 'sine', .012], [196, 'triangle', .006]],
      hospital: [[58, 'sine', .025], [116, 'sine', .008], [232, 'triangle', .004]]
    };
    for (const [frequency, type, volume] of profiles[this.template] || profiles.warehouse) {
      const oscillator = this.context.createOscillator();
      const gain = this.context.createGain();
      oscillator.type = type; oscillator.frequency.value = frequency; gain.gain.value = volume;
      oscillator.connect(gain).connect(this.master); oscillator.start();
      this.ambientNodes.push(oscillator);
    }
    this.sceneTimer = 2.5;
  }

  createNoiseBuffer() {
    const length = Math.floor(this.context.sampleRate * .16);
    const buffer = this.context.createBuffer(1, length, this.context.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < length; i += 1) data[i] = (Math.random() * 2 - 1) * (1 - i / length);
    return buffer;
  }

  createRobotMotor() {
    this.motor = this.context.createOscillator();
    this.motorGain = this.context.createGain();
    this.motorPan = this.context.createStereoPanner?.() || null;
    this.motor.type = 'sawtooth'; this.motor.frequency.value = 72; this.motorGain.gain.value = 0;
    if (this.motorPan) this.motor.connect(this.motorGain).connect(this.motorPan).connect(this.master);
    else this.motor.connect(this.motorGain).connect(this.master);
    this.motor.start();
  }

  toggle() {
    this.muted = !this.muted;
    if (this.master) this.master.gain.setTargetAtTime(this.muted ? 0 : .28, this.context.currentTime, .03);
    return !this.muted;
  }

  update(delta, player, simulation, scene) {
    if (!this.context || this.muted) return;
    this.beepTimer -= delta; this.stepTimer -= delta; this.sceneTimer -= delta;
    const nearest = simulation.robots.reduce((best, robot) => {
      const distance = Math.hypot(robot.position[0] - player.position[0], robot.position[2] - player.position[2]);
      return !best || distance < best.distance ? { robot, distance } : best;
    }, null);
    this.updateMotor(nearest, player);
    if (nearest && nearest.distance < 12 && this.beepTimer <= 0 && nearest.robot.blockedByHuman) {
      this.robotBeep(nearest.robot, nearest.distance, player); this.beepTimer = 1.25;
    }
    simulation.robots.forEach(robot => {
      const knownRobot = this.robotStates.has(robot.id);
      const previous = this.robotStates.get(robot.id) || { paused: false, mode: 'working', taskId: robot.activeTask?.id, avoiding: false, reservationBlocked: false };
      if (robot.pause > 0 && !previous.paused) this.operationCue(robot);
      if (robot.mode === 'charging' && previous.mode !== 'charging') this.chargingCue();
      if (previous.mode === 'fault' && robot.mode !== 'fault') this.recoveryCue();
      if (knownRobot && robot.activeTask && previous.taskId !== robot.activeTask.id) this.dispatchCue(robot);
      if (robot.avoidingHuman && !previous.avoiding) this.avoidanceCue();
      if (robot.reservationBlocked && !previous.reservationBlocked) this.trafficCue();
      this.robotStates.set(robot.id, { paused: robot.pause > 0, mode: robot.mode, taskId: robot.activeTask?.id, avoiding: robot.avoidingHuman, reservationBlocked: robot.reservationBlocked });
    });
    if (player.moving && !player.flying && this.stepTimer <= 0) {
      const outside = Math.abs(player.position[0]) > scene.config.width / 2 || Math.abs(player.position[2]) > scene.config.depth / 2;
      this.footstep(outside); this.stepTimer = player.sprinting ? .27 : .41;
    }
    if (this.sceneTimer <= 0) {
      this.sceneCue(); this.sceneTimer = this.template === 'airport' ? 11 : this.template === 'hospital' ? 7 : 9;
    }
  }

  updateMotor(nearest, player) {
    if (!nearest || nearest.distance > 15) { this.motorGain.gain.setTargetAtTime(0, this.context.currentTime, .08); return; }
    if (nearest.robot.mode === 'fault') {
      this.motorGain.gain.setTargetAtTime(0, this.context.currentTime, .05);
      return;
    }
    if (nearest.robot.mode === 'charging') {
      const volume = Math.max(0, (1 - nearest.distance / 15) * .035);
      this.motor.frequency.setTargetAtTime(164, this.context.currentTime, .08);
      this.motorGain.gain.setTargetAtTime(volume, this.context.currentTime, .08);
      return;
    }
    const speedRatio = nearest.robot.currentSpeed / Math.max(.1, nearest.robot.route.speed);
    const drive = nearest.robot.drive || 'electric';
    const driveVolume = drive === 'traction' ? .018 : drive === 'quiet' ? -.014 : 0;
    const baseFrequency = drive === 'traction' ? 46 : drive === 'quiet' ? 92 : 58;
    const volume = Math.max(0, (1 - nearest.distance / 15) * (.035 + driveVolume + speedRatio * .055));
    this.motor.frequency.setTargetAtTime(baseFrequency + speedRatio * (drive === 'quiet' ? 78 : 62), this.context.currentTime, .05);
    this.motorGain.gain.setTargetAtTime(volume, this.context.currentTime, .06);
    if (this.motorPan) this.motorPan.pan.setTargetAtTime(Math.max(-1, Math.min(1, (nearest.robot.position[0] - player.position[0]) / 8)), this.context.currentTime, .05);
  }

  tone(frequency, duration, volume, type = 'sine', delay = 0) {
    const now = this.context.currentTime + delay;
    const oscillator = this.context.createOscillator(); const gain = this.context.createGain();
    oscillator.type = type; oscillator.frequency.value = frequency;
    gain.gain.setValueAtTime(volume, now); gain.gain.exponentialRampToValueAtTime(.0001, now + duration);
    oscillator.connect(gain).connect(this.master); oscillator.start(now); oscillator.stop(now + duration + .02);
  }

  operationCue(robot) {
    const base = robot.kind === 'medical' ? 660 : robot.kind === 'baggage' ? 440 : 520;
    this.tone(base, .10, .035); this.tone(base * 1.25, .14, .028, 'sine', .11);
  }

  chargingCue() {
    this.tone(294, .18, .025, 'sine');
    this.tone(440, .28, .022, 'sine', .16);
    this.tone(587, .38, .018, 'sine', .34);
  }

  dispatchCue(robot) {
    const base = robot.kind === 'medical' ? 620 : robot.kind === 'baggage' ? 480 : 540;
    this.tone(base, .08, .024, 'square');
    this.tone(base * 1.5, .12, .020, 'sine', .09);
  }

  avoidanceCue() {
    this.tone(390, .08, .016, 'sine');
    this.tone(465, .08, .014, 'sine', .11);
  }

  trafficCue() {
    this.tone(350, .07, .012, 'triangle');
    this.tone(350, .07, .010, 'triangle', .13);
  }

  recoveryCue() {
    this.tone(440, .10, .020, 'sine');
    this.tone(660, .18, .018, 'sine', .11);
  }

  scenarioEvent(type) {
    if (!this.context || this.muted) return;
    if (type === 'robot-fault') {
      this.tone(220, .16, .045, 'sawtooth');
      this.tone(165, .24, .035, 'square', .18);
    } else {
      this.tone(520, .09, .028, 'square');
      this.tone(690, .12, .024, 'square', .11);
      this.tone(820, .16, .020, 'sine', .24);
    }
  }

  sceneCue() {
    if (this.template === 'airport') {
      this.tone(523, .45, .018); this.tone(659, .55, .015, 'sine', .28); this.tone(784, .75, .012, 'sine', .56);
    } else if (this.template === 'hospital') {
      this.tone(880, .09, .014); this.tone(880, .09, .012, 'sine', .18);
    } else {
      this.tone(310, .11, .018, 'square'); this.tone(260, .14, .015, 'square', .16);
    }
  }

  robotBeep(robot, distance, player) {
    const now = this.context.currentTime; const oscillator = this.context.createOscillator(); const gain = this.context.createGain();
    const pan = this.context.createStereoPanner?.(); oscillator.type = 'square';
    oscillator.frequency.setValueAtTime(robot.kind === 'medical' ? 740 : robot.kind === 'baggage' ? 520 : 620, now);
    oscillator.frequency.exponentialRampToValueAtTime(oscillator.frequency.value * .82, now + .13);
    const volume = Math.max(.012, .075 * (1 - distance / 14));
    gain.gain.setValueAtTime(volume, now); gain.gain.exponentialRampToValueAtTime(.0001, now + .16);
    if (pan) { pan.pan.value = Math.max(-1, Math.min(1, (robot.position[0] - player.position[0]) / 7)); oscillator.connect(gain).connect(pan).connect(this.master); }
    else oscillator.connect(gain).connect(this.master);
    oscillator.start(now); oscillator.stop(now + .17);
  }

  footstep(outside) {
    if (!this.noiseBuffer) return;
    const source = this.context.createBufferSource(); const filter = this.context.createBiquadFilter(); const gain = this.context.createGain();
    source.buffer = this.noiseBuffer; filter.type = 'lowpass'; filter.frequency.value = outside ? 310 : 720; gain.gain.value = outside ? .075 : .052;
    source.connect(filter).connect(gain).connect(this.master); source.start();
  }
}
