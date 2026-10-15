import { api } from "./api";

export const workspace = {
  runs: id => api.get(`/api/workspace/offices/${id}/runs`).then(r => r.data),
  run: (id, run) => api.get(`/api/workspace/offices/${id}/runs/${run}`).then(r => r.data),
  createRun: (id, body) => api.post(`/api/workspace/offices/${id}/runs`, body).then(r => r.data),
  retryRun: (id, run) => api.post(`/api/workspace/offices/${id}/runs/${run}/retry`).then(r => r.data),
  me: () => api.get("/api/workspace/me").then(r => r.data),
  offices: () => api.get("/api/workspace/offices").then(r => r.data),
  createOffice: name => api.post("/api/workspace/offices", { name }).then(r => r.data),
  members: id => api.get(`/api/workspace/offices/${id}/members`).then(r => r.data),
  enroll: (id, body) => api.post(`/api/workspace/offices/${id}/members`, body),
  records: id => api.get(`/api/workspace/offices/${id}/records`).then(r => r.data),
  saveRecord: (id, body, record) => (record
    ? api.put(`/api/workspace/offices/${id}/records/${record.id}`, { ...body, expected_revision: record.revision })
    : api.post(`/api/workspace/offices/${id}/records`, body)).then(r => r.data),
  advisories: id => api.get(`/api/workspace/offices/${id}/advisories`).then(r => r.data),
  saveAdvisory: (id, body, version) => (version
    ? api.put(`/api/workspace/offices/${id}/advisories/${version.advisory_id}`, { ...body, expected_version: version.version })
    : api.post(`/api/workspace/offices/${id}/advisories`, body)).then(r => r.data),
  transition: (id, version, action, reason) => api.post(
    `/api/workspace/offices/${id}/advisories/${version.advisory_id}/transition`,
    { action, expected_version: version.version, reason }),
  events: (id, entity) => api.get(`/api/workspace/offices/${id}/events`, { params: { entity_id: entity } }).then(r => r.data),
  released: () => api.get("/api/workspace/released").then(r => r.data),
  audio: (id, language) => api.post(`/api/workspace/released/${id}/audio`, null,
    { params: { language }, responseType: "blob" }).then(r => r.data),
};

export function workspaceError(error) {
  const detail = error.response?.data?.detail;
  return typeof detail === "string" ? detail : "Unable to save. Check the fields and reload if the record changed.";
}
