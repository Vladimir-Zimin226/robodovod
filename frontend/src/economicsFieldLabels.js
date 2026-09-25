import { fieldPresentation } from './presentation';

export function economicsFieldLabel(server) {
  return fieldPresentation(server).label;
}

export function economicsFieldAction(server) {
  return fieldPresentation(server).action;
}
