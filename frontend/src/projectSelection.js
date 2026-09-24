const keyFor = (userId) => `robodovod.active-project.${userId}`;

export function readRememberedProjectId(storage, userId) {
  try {
    return userId ? storage.getItem(keyFor(userId)) : null;
  } catch {
    return null;
  }
}

export function rememberProjectId(storage, userId, projectId) {
  if (!userId || !projectId) return;
  try {
    storage.setItem(keyFor(userId), projectId);
  } catch {
    // The current tab can still use its in-memory project when storage is disabled.
  }
}

export function forgetProjectId(storage, userId) {
  if (!userId) return;
  try {
    storage.removeItem(keyFor(userId));
  } catch {
    // Logout still clears the in-memory project.
  }
}

export function selectRestorableProject(projects, rememberedId) {
  if (!Array.isArray(projects)) return null;
  const remembered = projects.find((project) => project.id === rememberedId);
  if (remembered) return remembered;
  return projects.length === 1 ? projects[0] : null;
}
