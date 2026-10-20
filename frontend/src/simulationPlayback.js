// The server supplies authoritative pose samples. This module only interpolates their display.
export function playbackPose(samples, elapsedSeconds) {
  if (!Array.isArray(samples) || samples.length === 0) return null;
  const first = samples[0];
  const heading = (from, to) => Math.atan2(to.y_m - from.y_m, to.x_m - from.x_m);
  if (elapsedSeconds <= first.t_s) return [first.x_m, first.y_m,
    samples.length > 1 ? heading(first, samples[1]) : 0];
  for (let i = 1; i < samples.length; i += 1) {
    const next = samples[i];
    if (elapsedSeconds > next.t_s) continue;
    const previous = samples[i - 1];
    const duration = next.t_s - previous.t_s;
    const fraction = duration > 0 ? (elapsedSeconds - previous.t_s) / duration : 1;
    return [previous.x_m + (next.x_m - previous.x_m) * fraction,
      previous.y_m + (next.y_m - previous.y_m) * fraction, heading(previous, next)];
  }
  const last = samples[samples.length - 1];
  return [last.x_m, last.y_m, samples.length > 1 ? heading(samples[samples.length - 2], last) : 0];
}

export function playbackDuration(samples) {
  return Array.isArray(samples) && samples.length ? samples[samples.length - 1].t_s : 0;
}

export function advancePlaybackTime(elapsed, wallSeconds, rate, duration) {
  if (![1, 2, 4, 8].includes(rate)) throw new RangeError('unsupported playback rate');
  return Math.min(duration, elapsed + Math.max(0, wallSeconds) * rate);
}
