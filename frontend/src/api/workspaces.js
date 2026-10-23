import { apiRequest } from "./client.js";

export function listWorkspaces() {
    return apiRequest("/workspaces/");
}

export function createWorkspace(name) {
    return apiRequest("/workspaces/", {method: 'POST', data: {name: name}});
}

export function getWorkspace(id) {
    return apiRequest(`/workspaces/${id}`);
}