const paths = {
  home: <><path d="M3 11.5 12 4l9 7.5"/><path d="M5.5 10v10h13V10M9 20v-6h6v6"/></>,
  process: <><circle cx="6" cy="6" r="2"/><circle cx="18" cy="18" r="2"/><path d="M8 6h5a3 3 0 0 1 3 3v1M16 14v1a3 3 0 0 1-3 3H8"/><path d="m16 7 2 3-3 1M8 15l-2 3 3 1"/></>,
  cube: <><path d="m12 3 8 4.5v9L12 21l-8-4.5v-9Z"/><path d="m4.5 7.8 7.5 4.3 7.5-4.3M12 12v9"/></>,
  chart: <><path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/></>,
  calculator: <><rect x="5" y="2.5" width="14" height="19" rx="2"/><path d="M8 6h8v4H8zM8.5 14h1M12 14h1M15.5 14h1M8.5 18h1M12 18h1M15.5 18h1"/></>,
  money: <><circle cx="12" cy="12" r="9"/><path d="M15.5 8.5c-.8-.8-2-1.2-3.5-1.2-2 0-3.4 1-3.4 2.5 0 3.8 6.8 1.8 6.8 5.6 0 1.4-1.3 2.5-3.4 2.5-1.6 0-3-.5-4-1.5M12 5.5v13"/></>,
  report: <><path d="M6 3h9l4 4v14H6z"/><path d="M14 3v5h5M9 13h6M9 17h6"/></>,
  library: <><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H11v16H6.5A2.5 2.5 0 0 0 4 21.5zM20 5.5A2.5 2.5 0 0 0 17.5 3H13v16h4.5a2.5 2.5 0 0 1 2.5 2.5z"/></>,
  search: <><circle cx="10.5" cy="10.5" r="6.5"/><path d="m15.5 15.5 5 5"/></>,
  arrow: <><path d="M5 12h14M14 7l5 5-5 5"/></>,
  warning: <><path d="M12 3 2.8 20h18.4z"/><path d="M12 9v4M12 17h.01"/></>,
  check: <path d="m5 12 4 4L19 6"/>,
  menu: <><path d="M4 7h16M4 12h16M4 17h16"/></>,
  close: <><path d="m6 6 12 12M18 6 6 18"/></>,
  warehouse: <><path d="M3 9 12 4l9 5v11H3z"/><path d="M3 9h18M7 20v-8h10v8M10 12v8M14 12v8"/></>,
  airport: <><path d="M3 20h18M5 20V9h14v11M8 9V6h8v3M10 6V4h4v2M8 13h2m4 0h2m-8 3h2m4 0h2"/><path d="m3 8 3-2m15 2-3-2"/></>,
  clinic: <><path d="M4 20V5h16v15M3 20h18M9 20v-5h6v5M10 8h4m-2-2v4M7 12h2m6 0h2"/></>,
  assistant: <><path d="M5 5.5A3.5 3.5 0 0 1 8.5 2h7A3.5 3.5 0 0 1 19 5.5v10a3.5 3.5 0 0 1-3.5 3.5H9l-4 3v-6.5z"/><path d="M9 10h.01M15 10h.01M9.5 14c1.5 1.2 3.5 1.2 5 0"/></>,
  forklift_driver: <><path d="M3 5v14h12M3 14h7l2 4M10 10h4v6h-2M17 4v13h5M17 17h5M5 19a2 2 0 1 0 4 0M13 19a2 2 0 1 0 4 0"/></>,
  loader: <><path d="M4 8 12 4l8 4v9l-8 4-8-4zM4 8l8 4 8-4M12 12v9M7 6.5l8 4"/></>,
  storekeeper: <><path d="M3 20V5h18v15M3 10h18M3 15h18M8 10V6m8 4V6M6 20v-5m6 5v-5m6 5v-5"/></>,
  picker: <><path d="M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM14 16l2 2 4-5"/></>,
  sorter: <><path d="M3 5h18M12 5v5M12 10l-6 5m6-5 6 5M3 15h6v5H3zM15 15h6v5h-6z"/></>,
  packer: <><path d="M3 7 12 3l9 4v11l-9 4-9-4zM3 7l9 4 9-4M12 11v11M8 5l9 4"/></>,
  cleaner: <><path d="M6 21 14 4M12 8l5 2M4 21h9M17 17l1-2 1 2 2 1-2 1-1 2-1-2-2-1z"/></>,
  inventory_worker: <><path d="M5 3h14v18H5zM8 3v3h8V3M8 11h3m-3 4h3m3-4h3m-3 4h3M8 19h8"/></>,
};

export default function AppIcon({ name, size = 20, className = '' }) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {paths[name] || paths.cube}
    </svg>
  );
}
