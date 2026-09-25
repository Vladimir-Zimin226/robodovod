const STAGES = [
  ['PICKING', ['picking_lines', 'picking_items']],
  ['BUFFER', ['tote_handoff']],
  ['FEED_TO_PACK', ['tote_handoff']],
  ['PACKAGING', ['packaging']],
];

function pathToShipping(conversions, start) {
  const byFrom = new Map();
  for (const item of conversions.filter((entry) => entry.confirmed)) {
    byFrom.set(item.from_code, [...(byFrom.get(item.from_code) || []), item]);
  }
  const walk = (code, seen) => {
    if (code === 'shipping') return [];
    const priority = { tote_handoff: 0, packaging: 1, shipping: 2 };
    const edges = [...(byFrom.get(code) || [])].sort((a, b) =>
      (priority[a.to_code] ?? 3) - (priority[b.to_code] ?? 3));
    for (const edge of edges) {
      if (seen.has(edge.to_code)) continue;
      const tail = walk(edge.to_code, new Set([...seen, edge.to_code]));
      if (tail) return [edge, ...tail];
    }
    return null;
  };
  return walk(start, new Set([start]));
}

export function qualifiedWarehouseStages(chain, rates, palletDemand = null) {
  if (chain?.schema_version !== 'warehouse-chain-v1' || chain.version < 1) return [];
  const flows = new Map(chain.flows.map((flow) => [flow.code, flow]));
  const resources = new Map(chain.resources.map((resource) => [resource.resource_id, resource]));
  const output = [];
  const usedResources = new Set();
  for (const [code, candidates] of STAGES) {
    const rate = Number(rates?.[code]);
    if (!Number.isFinite(rate) || rate <= 0) continue;
    const qualified = candidates.map((candidate) => {
      const flow = flows.get(candidate);
      const path = flow?.confirmed && flow.value ? pathToShipping(chain.conversions, flow.code) : null;
      const factor = path?.reduce((value, edge) => value * Number(edge.factor), 1);
      const resource = flow?.resource_ids.map((id) => resources.get(id)).find((item) => item?.confirmed
        && ['STAFF', 'EQUIPMENT', 'CONVEYOR'].includes(item.kind) && !usedResources.has(item.resource_id)
        && Number.isInteger(Number(item.amount)) && Number(item.amount) > 0 && Number(item.amount) <= 100);
      return { flow, path, factor, resource };
    }).find(({ flow, path, factor, resource }) => flow && path?.length && resource
      && Number.isFinite(factor) && factor > 0
      && (palletDemand === null || Math.abs(Number(flow.value) * factor - palletDemand) <= Math.max(0.01, palletDemand * 0.001)));
    if (!qualified) continue;
    const { flow, path, factor, resource } = qualified;
    usedResources.add(resource.resource_id);
    output.push({
      stage: code, flow_code: flow.code, units_per_pallet: String(1 / factor),
      service_rate_per_hour: String(rate), capacity: Number(resource.amount), resource_id: resource.resource_id,
      resource_kind: resource.kind === 'STAFF' ? 'HUMAN' : flow.solution === 'CATALOG' ? 'ROBOT' : 'EQUIPMENT',
      source_ref: `input.simulation.rate.${code.toLowerCase()}`,
      conversion_refs: path.map((edge) => `conversion.${edge.from_code}.${edge.to_code}`),
    });
  }
  for (let index = output.length - 1; index > 0; index -= 1) {
    const earlier = output[index - 1];
    const later = output[index];
    if (earlier.flow_code !== later.flow_code
        && !earlier.conversion_refs.some((ref) => ref.endsWith(`.${later.flow_code}`))) output.splice(index, 1);
  }
  return output;
}

export async function buildExtendedSimulationRequest(base, envelope, rates) {
  if (base?.schema_version !== 'simulation-request-v2' || !envelope?.chain_digest) return null;
  const stages = qualifiedWarehouseStages(envelope.chain, rates, Number(base.scenario_spec.tasks?.[0]?.demand?.value));
  if (!stages.length) return null;
  const process_chain = {
    schema_version: 'warehouse-process-chain-v2',
    warehouse_chain_version: envelope.chain.version,
    warehouse_chain_digest: envelope.chain_digest,
    stages,
  };
  const bytes = new TextEncoder().encode(JSON.stringify(process_chain));
  const hash = await crypto.subtle.digest('SHA-256', bytes);
  const suffix = [...new Uint8Array(hash)].slice(0, 8).map((byte) => byte.toString(16).padStart(2, '0')).join('');
  return { ...base, request_id: `${base.request_id}.chain.${suffix}`, process_chain };
}
