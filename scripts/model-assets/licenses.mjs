/** NC assets need an explicit noncommercial delivery decision. */
export function canPublish(entry) {
  if (entry.reviewOnly) return false;
  return ['CC0', 'CC-BY 3.0', 'CC-BY 4.0'].includes(entry.license) ||
    (entry.nonCommercial === true && ['CC-BY-NC 4.0', 'CC-BY-NC-SA 4.0'].includes(entry.license));
}

export const LOCAL_LICENSES = ['CC0', 'CC-BY 3.0', 'CC-BY 4.0', 'CC-BY-NC 4.0', 'CC-BY-NC-SA 4.0', 'Sketchfab Free Standard'];
