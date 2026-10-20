export class SceneSaveConflict extends Error {
  constructor(currentRevision) {
    super('Сцена изменена в другой вкладке. Загрузите актуальную версию перед сохранением.');
    this.currentRevision = currentRevision;
  }
}

export class RobCraftProjectStore {
  constructor(projectId, fetcher = (...args) => fetch(...args), csrfToken = () => '') {
    if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(projectId)) throw new TypeError('Неверный ID проекта');
    this.url = `/api/projects/${projectId}/robcraft-scene`;
    this.fetcher = fetcher;
    this.csrfToken = csrfToken;
    this.revision = 0;
    this.name = null;
    this.versions = [];
  }

  async load() {
    const response = await this.fetcher(this.url, { credentials: 'include' });
    if (!response.ok) throw new Error(`Не удалось открыть сцену проекта: HTTP ${response.status}`);
    const data = await response.json();
    this.revision = data.revision;
    this.name = data.name;
    this.versions = data.versions || [];
    return data.document;
  }

  async save(document, name) {
    const response = await this.fetcher(this.url, {
      method: 'PUT', credentials: 'include', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': this.csrfToken() },
      body: JSON.stringify({ expected_revision: this.revision, name, document })
    });
    if (response.status === 409) {
      const payload = await response.json();
      throw new SceneSaveConflict(payload.detail?.current_revision);
    }
    if (!response.ok) throw new Error(`Не удалось сохранить сцену проекта: HTTP ${response.status}`);
    const data = await response.json();
    this.revision = data.revision;
    this.name = data.name;
    this.versions = [...this.versions, data].slice(-8);
    return data;
  }

  async saveAs(document, name) {
    const response = await this.fetcher(`${this.url}/save-as`, {
      method: 'POST', credentials: 'include',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': this.csrfToken() },
      body: JSON.stringify({ expected_revision: this.revision, name, document })
    });
    if (response.status === 409) {
      const payload = await response.json();
      throw new SceneSaveConflict(payload.detail?.current_revision);
    }
    if (!response.ok) throw new Error(`Не удалось сохранить сцену как новый проект: HTTP ${response.status}`);
    return response.json();
  }

  async readVersion(revision) {
    const response = await this.fetcher(`${this.url}/versions/${revision}`, { credentials: 'include' });
    if (!response.ok) throw new Error(`Не удалось открыть версию: HTTP ${response.status}`);
    return response.json();
  }
}
