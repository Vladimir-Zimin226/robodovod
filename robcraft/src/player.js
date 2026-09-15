import { clamp } from './core/math.js';
import { circleIntersectsSolid } from './editor/collisions.js';

function intersects(x, z, radius, solid) {
  return circleIntersectsSolid(x, z, radius, solid);
}

export class Player {
  constructor(canvas) {
    this.canvas = canvas;
    this.position = [0, 1.72, 0];
    this.yaw = 0;
    this.pitch = 0;
    this.keys = new Set();
    this.radius = .34;
    this.enabled = false;
    this.flying = false;
    this.moving = false;
    this.sprinting = false;
    this.editorEnabled = false;
    document.addEventListener('keydown', event => this.keys.add(event.code));
    document.addEventListener('keyup', event => this.keys.delete(event.code));
    document.addEventListener('mousemove', event => {
      if (document.pointerLockElement !== canvas) return;
      this.yaw += event.movementX * .0022;
      this.pitch = clamp(this.pitch - event.movementY * .0018, -1.35, 1.35);
    });
    canvas.addEventListener('click', () => {
      if (this.enabled && !this.editorEnabled && document.pointerLockElement !== canvas) canvas.requestPointerLock();
    });
  }

  reset(spawn) {
    this.position = [...spawn];
    this.yaw = 0;
    this.pitch = -.03;
    this.flying = false;
  }

  toggleFlight() {
    this.flying = !this.flying;
    if (!this.flying) this.position[1] = 1.72;
    return this.flying;
  }

  update(delta, solids) {
    if (!this.enabled || document.pointerLockElement !== this.canvas) {
      this.moving = false;
      this.sprinting = false;
      return;
    }
    let forward = 0;
    let side = 0;
    if (this.keys.has('KeyW') || this.keys.has('ArrowUp')) forward += 1;
    if (this.keys.has('KeyS') || this.keys.has('ArrowDown')) forward -= 1;
    if (this.keys.has('KeyD') || this.keys.has('ArrowRight')) side += 1;
    if (this.keys.has('KeyA') || this.keys.has('ArrowLeft')) side -= 1;
    const magnitude = Math.hypot(forward, side) || 1;
    const sprinting = this.keys.has('ShiftLeft') || this.keys.has('ShiftRight');
    this.moving = forward !== 0 || side !== 0;
    this.sprinting = sprinting;
    const speed = this.flying ? (sprinting ? 15 : 8) : (sprinting ? 7.2 : 4.2);
    const dx = ((Math.sin(this.yaw) * forward) + (Math.cos(this.yaw) * side)) / magnitude * speed * delta;
    const dz = ((-Math.cos(this.yaw) * forward) + (Math.sin(this.yaw) * side)) / magnitude * speed * delta;
    const nextX = this.position[0] + dx;
    const nextZ = this.position[2] + dz;
    if (this.flying || !solids.some(solid => intersects(nextX, this.position[2], this.radius, solid))) this.position[0] = nextX;
    if (this.flying || !solids.some(solid => intersects(this.position[0], nextZ, this.radius, solid))) this.position[2] = nextZ;
    if (this.flying) {
      const vertical = (this.keys.has('Space') ? 1 : 0) - ((this.keys.has('ControlLeft') || this.keys.has('ControlRight')) ? 1 : 0);
      this.position[1] = clamp(this.position[1] + vertical * speed * delta, .7, 32);
    }
  }

  lookingAt(robots, maxDistance = 4.2) {
    const direction = [Math.sin(this.yaw) * Math.cos(this.pitch), -Math.cos(this.yaw) * Math.cos(this.pitch)];
    let best = null;
    for (const robot of robots) {
      const dx = robot.position[0] - this.position[0];
      const dz = robot.position[2] - this.position[2];
      const distance = Math.hypot(dx, dz);
      if (distance > maxDistance) continue;
      const dot = (dx / distance) * direction[0] + (dz / distance) * direction[1];
      if (dot > .82 && (!best || distance < best.distance)) best = { robot, distance };
    }
    return best?.robot || null;
  }
}
