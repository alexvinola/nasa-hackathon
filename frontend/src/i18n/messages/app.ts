// Messages of the "app" slice: page metadata. Same keys in both languages: the type of `en` enforces it.
const es = {
  "app.title": "PULSAR",
  "app.description": "Tu compañero personal de salud en el espacio.",
} as const;
const en: Record<keyof typeof es, string> = {
  "app.title": "PULSAR",
  "app.description": "Your personal health companion in space.",
};
export default { es, en };
