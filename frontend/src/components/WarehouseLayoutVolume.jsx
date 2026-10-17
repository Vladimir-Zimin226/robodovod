import { itemSize } from '../facilityLayout';

const COLOR = {
  rack: ['#608469', '#345346', '#9bb78c'],
  obstacle: ['#ba8170', '#85574e', '#e8ac8d'],
  no_go: ['#bc5f59', '#923f45', '#f19b85'],
  aisle: ['#2a5863', '#24434d', '#60b2bb'],
  charger: ['#7795d1', '#4a629b', '#c7d7f8'],
  pickup: ['#efc178', '#a97542', '#ffe0a3'],
  dropoff: ['#6ee4c9', '#378b82', '#a8fff0'],
  receiving: ['#327082', '#1b4857', '#7bd3df'],
  picking: ['#526a9b', '#354a78', '#a7c7ff'],
  packing: ['#826494', '#654a78', '#d9b8ed'],
  shipping: ['#368b78', '#275e59', '#8ef4d8'],
  staging: ['#927b4f', '#665438', '#e9cb8c'],
};
const HEIGHT = { rack: 25, obstacle: 21, no_go: 2, aisle: 1, charger: 12, pickup: 9, dropoff: 9,
  receiving: 2, picking: 2, packing: 2, shipping: 2, staging: 2 };
const polygon = (points) => points.map(([x, y]) => `${x},${y}`).join(' ');

export default function WarehouseLayoutVolume({ layout, route, robotPoint = null }) {
  const width = Number(layout.width_m), depth = Number(layout.depth_m);
  const sx = 8, sy = 3;
  const offsetX = depth * .72 * sx + 32;
  const project = (x, y, height = 0) => [offsetX + (x - y * .72) * sx, 50 + (x + y) * sy - height];
  const floor = [project(0, 0), project(width, 0), project(width, depth), project(0, depth)];
  const draw = [...(layout.items || [])].sort((a, b) => Number(a.x) + Number(a.y) - Number(b.x) - Number(b.y));
  const viewWidth = offsetX + width * sx + 34;
  const viewHeight = 50 + (width + depth) * sy + 52;
  return <svg className="warehouse-layout-volume" viewBox={`0 0 ${viewWidth} ${viewHeight}`}
    role="img" aria-label="Объёмный эскиз той же планировки и проверенного маршрута">
    <defs><linearGradient id="warehouse-volume-floor" x1="0" x2="1" y1="0" y2="1"><stop stopColor="#21404a" /><stop offset="1" stopColor="#10272e" /></linearGradient></defs>
    <polygon points={polygon([floor[3], floor[2], [floor[2][0], floor[2][1] + 13], [floor[3][0], floor[3][1] + 13]])} fill="#0b1920" />
    <polygon points={polygon([floor[1], floor[2], [floor[2][0], floor[2][1] + 13], [floor[1][0], floor[1][1] + 13]])} fill="#163039" />
    <polygon points={polygon(floor)} fill="url(#warehouse-volume-floor)" stroke="#6fa69d" strokeWidth="2" />
    {layout.imageData && <image href={layout.imageData} x="0" y="0" width={width} height={depth}
      preserveAspectRatio="none" opacity=".35" transform={`matrix(${sx} ${sy} ${-sx * .72} ${sy} ${offsetX} 50)`} />}
    {Array.from({ length: Math.floor(width / 5) }, (_, index) => (index + 1) * 5).map((x) =>
      <path key={`x-${x}`} d={`M${project(x, 0).join(' ')}L${project(x, depth).join(' ')}`} stroke="#456a70" strokeWidth=".5" />)}
    {Array.from({ length: Math.floor(depth / 5) }, (_, index) => (index + 1) * 5).map((y) =>
      <path key={`y-${y}`} d={`M${project(0, y).join(' ')}L${project(width, y).join(' ')}`} stroke="#456a70" strokeWidth=".5" />)}
    {route.status === 'READY' && <polyline points={polygon(route.path.map(({ x, y }) => project(x, y, 1)))}
      fill="none" stroke="#74ffcb" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />}
    {robotPoint && <circle cx={project(robotPoint.x, robotPoint.y, 3)[0]} cy={project(robotPoint.x, robotPoint.y, 3)[1]} r="7" fill="#d8ff83" stroke="#173c38" strokeWidth="2" />}
    {draw.map((item, index) => {
      const [w, d] = itemSize(item), h = HEIGHT[item.kind] || 10;
      const b = project(item.x + w, item.y);
      const c = project(item.x + w, item.y + d), e = project(item.x, item.y + d);
      const at = project(item.x, item.y, h), bt = project(item.x + w, item.y, h);
      const ct = project(item.x + w, item.y + d, h), et = project(item.x, item.y + d, h);
      const [top, side, edge] = COLOR[item.kind] || COLOR.obstacle;
      if (item.kind === 'rack') {
        const corners = [[item.x, item.y], [item.x + w, item.y], [item.x + w, item.y + d], [item.x, item.y + d]];
        return <g key={item.id || index}>
          <title>Стеллаж · условные стойки, балки и паллеты · {item.provenance === 'PROVIDED' ? 'контур из DXF' : 'схема пользователя или примера'}</title>
          <polygon points={polygon([project(item.x, item.y), b, c, e])} fill="#1a2529" opacity=".65" />
          {[.28, .58, .89].map((level) => {
            const shelf = corners.map(([cx, cy]) => project(cx, cy, h * level));
            const cargo = [
              project(item.x + w * .17, item.y + d * .15, h * level + 5),
              project(item.x + w * .78, item.y + d * .15, h * level + 5),
              project(item.x + w * .78, item.y + d * .8, h * level + 5),
              project(item.x + w * .17, item.y + d * .8, h * level + 5),
            ];
            return <g key={level}>
              <polygon points={polygon(shelf)} fill="#293d40" stroke="#e69b46" strokeWidth="2.4" />
              <polygon points={polygon(cargo)} fill={level === .58 ? '#b7824d' : '#9a7148'} stroke="#d6ae72" strokeWidth="1" />
              <path d={`M${shelf[0].join(' ')}L${shelf[1].join(' ')}M${shelf[3].join(' ')}L${shelf[2].join(' ')}`} fill="none" stroke="#f2ad53" strokeWidth="2" />
            </g>;
          })}
          {corners.map(([cx, cy], post) => <path key={post} d={`M${project(cx, cy).join(' ')}L${project(cx, cy, h).join(' ')}`}
            stroke="#1c3438" strokeWidth="4.2" strokeLinecap="square" />)}
          <path d={`M${at.join(' ')}L${bt.join(' ')}L${ct.join(' ')}L${et.join(' ')}`} fill="none" stroke="#d2974c" strokeWidth="2" />
        </g>;
      }
      return <g key={item.id || index}>
        <title>{item.kind} · {item.provenance === 'ASSUMED' ? 'учебное допущение' : item.provenance === 'PROVIDED' ? 'импорт DXF' : 'нанесено пользователем'}</title>
        <polygon points={polygon([b, c, ct, bt])} fill={side} stroke={edge} strokeWidth="1" />
        <polygon points={polygon([e, c, ct, et])} fill={side} stroke={edge} strokeWidth="1" />
        <polygon points={polygon([at, bt, ct, et])} fill={top} stroke={edge} strokeWidth="1.5" />
        {['pickup', 'dropoff', 'receiving', 'picking', 'packing', 'shipping', 'staging'].includes(item.kind) && <text x={project(item.x + w / 2, item.y + d / 2, h + 11)[0]}
          y={project(item.x + w / 2, item.y + d / 2, h + 11)[1]} textAnchor="middle" fill="#fff" fontSize="10" fontWeight="700">
          {({ pickup: 'ПРИЁМ', dropoff: 'ОТГРУЗКА', receiving: 'ПРИЁМКА', picking: 'КОМПЛЕКТАЦИЯ',
            packing: 'УПАКОВКА', shipping: 'ОТГРУЗКА', staging: 'БУФЕР' })[item.kind]}</text>}
      </g>;
    })}
    <text x="32" y={viewHeight - 13} fill="#b3d9d5" fontSize="11">Объёмный эскиз · геометрия из той же схемы · высота объектов условная</text>
  </svg>;
}
