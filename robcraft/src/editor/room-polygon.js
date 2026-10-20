import { validZonePolygon } from './map-view.js';

const cross = (a, b, c) => (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);

export function triangulateRoom(points) {
  if (!Array.isArray(points) || points.length < 3) return null;
  const signedArea = points.reduce((sum, point, index) => {
    const next = points[(index + 1) % points.length];
    return sum + point[0] * next[1] - next[0] * point[1];
  }, 0);
  if (Math.abs(signedArea) < 1) return null;
  const orientation = Math.sign(signedArea);
  const remaining = points.map((_, index) => index);
  const triangles = [];
  while (remaining.length > 3) {
    let ear = false;
    for (let index = 0; index < remaining.length; index += 1) {
      const previous = remaining[(index + remaining.length - 1) % remaining.length];
      const current = remaining[index];
      const next = remaining[(index + 1) % remaining.length];
      if (cross(points[previous], points[current], points[next]) * orientation <= 1e-7) continue;
      const containsVertex = remaining.some(candidate => candidate !== previous && candidate !== current && candidate !== next &&
        cross(points[previous], points[current], points[candidate]) * orientation >= -1e-7 &&
        cross(points[current], points[next], points[candidate]) * orientation >= -1e-7 &&
        cross(points[next], points[previous], points[candidate]) * orientation >= -1e-7);
      if (containsVertex) continue;
      triangles.push([previous, current, next]);
      remaining.splice(index, 1);
      ear = true;
      break;
    }
    if (!ear) return null;
  }
  triangles.push(remaining);
  return triangles;
}

export function validRoomPolygon(points, width, depth) {
  return validZonePolygon(points, width, depth) && triangulateRoom(points) !== null;
}
