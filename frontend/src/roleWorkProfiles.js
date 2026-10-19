export const ZERO_ROLE_BASIS = 'Консервативное проектное допущение: без замера трудозатрат экономия роли равна нулю.';
export const ZERO_ROLE_RESIDUAL = 'Работа этой роли сохраняется в сценарии; замещение роботом принято равным нулю.';
export const PRIMARY_ROLE_BASIS = 'Проектное допущение пользователя о доле заменяемых задач и выработке; требуется замер на объекте.';

export function primaryWorkEvidence(values, roleId) {
  const profile = values.roleWorkProfiles?.[roleId] || {};
  const source = profile.source === 'USER' ? 'USER' : 'ASSUMPTION';
  return {
    source,
    basis: profile.basis?.trim() || (source === 'ASSUMPTION' ? PRIMARY_ROLE_BASIS : ''),
    confirmed: profile.confirmed === true,
  };
}

export function buildRoleWorkProfiles(values, roleRefs, primaryRoleId) {
  if (values.robotizableShare === '' || !values.residualOperations || !primaryRoleId) return null;
  return roleRefs.map((roleId) => {
    if (roleId === primaryRoleId) return {
      role_id: roleId,
      robotizable_fraction: values.robotizableShare,
      manual_units_per_shift: values.manualUnitsPerShift || null,
      residual_operations: values.residualOperations,
      ...primaryWorkEvidence(values, roleId),
    };
    const profile = values.roleWorkProfiles?.[roleId] || {};
    const fraction = profile.fraction ?? '0';
    const zero = Number(fraction) === 0;
    return {
      role_id: roleId,
      robotizable_fraction: fraction,
      manual_units_per_shift: profile.manual || null,
      residual_operations: profile.residual?.trim() || (zero ? ZERO_ROLE_RESIDUAL : ''),
      source: profile.source === 'USER' ? 'USER' : 'ASSUMPTION',
      basis: profile.basis?.trim() || (zero ? ZERO_ROLE_BASIS : ''),
      confirmed: profile.confirmed === true,
    };
  });
}
