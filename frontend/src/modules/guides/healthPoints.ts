import type { V3 } from "./mannequin";
import type { Lang } from "@/i18n";
import hrp from "../../../../shared/hrp.json";

/**
 * The SALUD tab: nine points on the body, each tied to the official HRP "Risks Involving Human Physiology" it
 * covers (https://www.nasa.gov/hrp/risks/, pages read 2026-11-14). `problems` and `tools` only repeat what those
 * pages say (a tool is listed only when a page names it, otherwise `tools` says so); `self` and `mate` are PULSAR's
 * own wording (team assumption): generic first steps that always end in "tell the flight surgeon". Not clinical
 * guidance and not a medical device. PULSAR never judges any of this: none of it is measured.
 */
export type HealthTool = "arrows" | "probe" | "oxygen" | "pack" | "swab" | "band" | "load";

/** A text in both languages. */
export type Text = { es: string; en: string };
export function healthText(text: Text, lang: Lang): string;
export function healthText(text: Text[], lang: Lang): string[];
export function healthText(text: Text | Text[], lang: Lang) {
  return Array.isArray(text) ? text.map((item) => item[lang]) : text[lang];
}

export type HealthPoint = {
  id: string;
  label: Text;
  /** Ids in shared/hrp.json; the panel shows their official names. */
  risks: (keyof typeof hrp.risks)[];
  /** Where it sits on the standing figure (front view, so only x and y place the marker). */
  site: V3;
  /** The 3D picture: which tool the animation shows working on that zone. */
  tool: HealthTool;
  problems: Text[];
  tools: Text;
  self: Text[];
  mate: Text[];
  /** Detail pages of the risks, in the order of `risks`. */
  pages: string[];
};

const PAGE = "https://www.nasa.gov/reference/";

export const HEALTH_POINTS: HealthPoint[] = [
  {
    id: "head",
    label: { es: "Cabeza · equilibrio", en: "Head · balance" },
    risks: ["SENSORIMOTOR_VESTIBULAR"],
    site: [0, 1.66, 0.2],
    tool: "arrows",
    problems: [{ es: "Mareo y náuseas por el movimiento", en: "Motion sickness and nausea" }, { es: "Desorientación y pérdida de equilibrio", en: "Disorientation and loss of balance" }, { es: "Torpeza entre la mano y el ojo; cuesta manejar mandos", en: "Poor hand-eye coordination; controls are hard to operate" }],
    tools: { es: "La NASA no tiene aún una contramedida establecida: investiga medicación contra el mareo, entrenamiento y ayudas de orientación.", en: "NASA does not yet have an established countermeasure: it is researching anti-motion-sickness medication, training and orientation aids." },
    self: [
      { es: "Detén lo que haces y sujétate a un punto fijo.", en: "Stop what you are doing and hold on to a fixed point." },
      { es: "Fija la vista en un punto estable y mueve la cabeza despacio.", en: "Fix your eyes on a steady point and move your head slowly." },
      { es: "No uses mandos ni hagas tareas críticas hasta que pase.", en: "Do not use controls or do critical tasks until it passes." },
      { es: "Avisa a la tripulación y al cirujano de vuelo; toma medicación solo si él te lo indica.", en: "Tell the crew and the flight surgeon; take medication only if the flight surgeon says so." },
    ],
    mate: [
      { es: "Sujétalo para que no flote ni se golpee.", en: "Hold on to them so they do not float off or get hurt." },
      { es: "Háblale despacio y pregúntale cómo se siente.", en: "Talk to them slowly and ask how they feel." },
      { es: "Aléjalo de los mandos y de las tareas críticas.", en: "Keep them away from the controls and from critical tasks." },
      { es: "Avisa al cirujano de vuelo y sigue sus instrucciones.", en: "Tell the flight surgeon and follow their instructions." },
    ],
    pages: [`${PAGE}risk-of-altered-sensorimotor-and-vestibular-function/`],
  },
  {
    id: "eyes",
    label: { es: "Ojos · visión", en: "Eyes · vision" },
    risks: ["SANS"],
    site: [-0.24, 1.42, 0.2],
    tool: "probe",
    problems: [{ es: "Cambios en la visión", en: "Changes in vision" }, { es: "Hinchazón del nervio óptico y pliegues en la retina", en: "Swelling of the optic nerve and folds in the retina" }, { es: "Más probable en misiones largas", en: "More likely on long missions" }],
    tools: { es: "No hay contramedida probada. Se usa un fundoscopio para ver la retina; se investigan suplementos y formas mecánicas de revertir el desplazamiento de líquidos hacia la cabeza.", en: "There is no proven countermeasure. A fundoscope is used to look at the retina; supplements and mechanical ways of reversing the shift of fluids toward the head are being researched." },
    self: [
      { es: "Anota cuándo notas un cambio en la visión y cómo es.", en: "Write down when you notice a change in your vision and what it is like." },
      { es: "No te frotes los ojos.", en: "Do not rub your eyes." },
      { es: "Avisa al cirujano de vuelo y pide el examen de retina con el fundoscopio.", en: "Tell the flight surgeon and ask for the retina exam with the fundoscope." },
      { es: "Evita tareas que exijan vista fina hasta que te revisen.", en: "Avoid tasks that need fine vision until you have been checked." },
    ],
    mate: [
      { es: "Pregúntale qué ve distinto y desde cuándo.", en: "Ask what looks different to them and since when." },
      { es: "Pídele que no se frote los ojos.", en: "Ask them not to rub their eyes." },
      { es: "Avisa al cirujano de vuelo; ayúdale a preparar el fundoscopio si te lo piden.", en: "Tell the flight surgeon; help set up the fundoscope if asked." },
      { es: "Quédate con él si ha de hacer tareas delicadas.", en: "Stay with them if they have to do delicate tasks." },
    ],
    pages: [`${PAGE}risk-of-spaceflight-associated-neuro-ocular-syndrome-sans/`],
  },
  {
    id: "heart",
    label: { es: "Corazón · circulación", en: "Heart · circulation" },
    risks: ["CARDIOVASCULAR_ADAPTATIONS"],
    site: [0.16, 0.72, 0.25],
    tool: "probe",
    problems: [{ es: "Latido irregular (arritmia)", en: "Irregular heartbeat (arrhythmia)" }, { es: "Coágulos de sangre", en: "Blood clots" }, { es: "Presión baja y riesgo de desmayo al volver a la gravedad", en: "Low blood pressure and risk of fainting on return to gravity" }],
    tools: { es: "Ejercicio regular, dieta sana, prendas de compresión en las piernas, beber mucho líquido antes de aterrizar y un ecógrafo para ver el corazón.", en: "Regular exercise, a healthy diet, compression garments on the legs, drinking plenty of fluid before landing and an ultrasound scanner to see the heart." },
    self: [
      { es: "Detente y sujétate en una posición segura.", en: "Stop and hold on in a safe position." },
      { es: "Cuenta tu pulso en la muñeca (mira la pestaña MEDIR).", en: "Count your pulse at the wrist (see the MEASURE tab)." },
      { es: "Avisa a la tripulación; si hay dolor en el pecho o te desmayas, avisa de inmediato al cirujano de vuelo.", en: "Tell the crew; if you have chest pain or faint, tell the flight surgeon immediately." },
      { es: "Si el cirujano lo pide, usa el ecógrafo para que vea tu corazón.", en: "If the flight surgeon asks, use the ultrasound scanner so they can see your heart." },
    ],
    mate: [
      { es: "Comprueba si responde y si respira.", en: "Check whether they respond and whether they are breathing." },
      { es: "Busca el pulso en su muñeca (pestaña MEDIR).", en: "Find the pulse at their wrist (MEASURE tab)." },
      { es: "Avisa ya al cirujano de vuelo y a la tripulación.", en: "Tell the flight surgeon and the crew right away." },
      { es: "Si no respira, sigue el protocolo de reanimación que te indique el cirujano de vuelo.", en: "If they are not breathing, follow the resuscitation protocol the flight surgeon gives you." },
    ],
    pages: [`${PAGE}risk-of-cardiovascular-adaptations/`],
  },
  {
    id: "lungs",
    label: { es: "Pulmones · oxígeno y presión", en: "Lungs · oxygen and pressure" },
    risks: ["HYPOXIA", "DECOMPRESSION_SICKNESS"],
    site: [-0.2, 0.58, 0.25],
    tool: "oxygen",
    problems: [{ es: "Confusión, dolor de cabeza y visión alterada (poco oxígeno)", en: "Confusion, headache and altered vision (low oxygen)" }, { es: "Dificultad para dormir", en: "Trouble sleeping" }, { es: "Dolor intenso y dificultad para respirar tras pasar a menor presión (descompresión)", en: "Severe pain and difficulty breathing after moving to lower pressure (decompression)" }],
    tools: { es: "Protocolos que equilibran oxígeno y presión, respirar oxígeno puro antes de un paseo espacial y el protocolo para terminar el paseo y volver a la nave deprisa pero con seguridad.", en: "Protocols that balance oxygen and pressure, breathing pure oxygen before a spacewalk and the protocol to end the spacewalk and return to the spacecraft quickly but safely." },
    self: [
      { es: "Detén el esfuerzo y avisa a la tripulación.", en: "Stop the effort and tell the crew." },
      { es: "Vuelve a una zona con presión y oxígeno normales siguiendo el protocolo.", en: "Return to an area with normal pressure and oxygen, following the protocol." },
      { es: "Usa el oxígeno de la nave si el procedimiento lo indica.", en: "Use the oxygen of the spacecraft if the procedure says so." },
      { es: "Avisa al cirujano de vuelo y anota qué sentías y cuándo empezó.", en: "Tell the flight surgeon and write down what you felt and when it started." },
    ],
    mate: [
      { es: "Ponlo a salvo en una zona con presión y oxígeno normales.", en: "Move them to safety in an area with normal pressure and oxygen." },
      { es: "Dale el oxígeno si el procedimiento o el cirujano lo indican.", en: "Give them oxygen if the procedure or the flight surgeon says so." },
      { es: "Si hizo un paseo espacial, díselo al cirujano de vuelo.", en: "If they did a spacewalk, tell the flight surgeon." },
      { es: "Quédate con él y sigue las instrucciones del cirujano de vuelo.", en: "Stay with them and follow the instructions of the flight surgeon." },
    ],
    pages: [`${PAGE}risk-of-hypoxia/`, `${PAGE}risk-of-decompression-sickness/`],
  },
  {
    id: "gut",
    label: { es: "Abdomen · comida y microbios", en: "Abdomen · food and microbes" },
    risks: ["FOOD_AND_NUTRITION", "HOST_MICROORGANISM"],
    site: [0, 0.1, 0.25],
    tool: "pack",
    problems: [{ es: "Comer poco o siempre lo mismo", en: "Eating too little or always the same thing" }, { es: "Cambios en los microbios del intestino y de la piel", en: "Changes in gut and skin microbes" }, { es: "Más riesgo de enfermar", en: "Higher risk of getting sick" }],
    tools: { es: "Un sistema de comida mejorado (más variedad, menos sodio; más de 200 alimentos y bebidas en la ISS) y muestras biológicas y de superficies para vigilar los microbios.", en: "An improved food system (more variety, less sodium; more than 200 foods and drinks on the ISS) and biological and surface samples to monitor microbes." },
    self: [
      { es: "Come lo planificado y varía el menú.", en: "Eat what is planned and vary the menu." },
      { es: "Si pierdes el apetito o te duele el abdomen, anótalo.", en: "If you lose your appetite or your abdomen hurts, write it down." },
      { es: "Lávate las manos o usa toallitas antes de comer.", en: "Wash your hands or use wipes before eating." },
      { es: "Avisa al cirujano de vuelo si dura más de un día.", en: "Tell the flight surgeon if it lasts more than a day." },
    ],
    mate: [
      { es: "Pregúntale qué ha comido y cómo se siente.", en: "Ask what they have eaten and how they feel." },
      { es: "Ayúdale a preparar comida que le apetezca.", en: "Help them prepare food they feel like eating." },
      { es: "Evita compartir utensilios si está enfermo.", en: "Avoid sharing utensils if they are sick." },
      { es: "Avisa al cirujano de vuelo si no mejora.", en: "Tell the flight surgeon if they do not get better." },
    ],
    pages: [`${PAGE}risk-of-inadequate-food-and-nutrition/`, `${PAGE}risk-of-host-microorganism-interactions/`],
  },
  {
    id: "skin",
    label: { es: "Piel · defensas", en: "Skin · defenses" },
    risks: ["ALTERED_IMMUNE_RESPONSE"],
    site: [-0.56, 0.4, 0.1],
    tool: "swab",
    problems: [{ es: "Erupciones y alergias poco habituales", en: "Unusual rashes and allergies" }, { es: "Reactivación de virus latentes (herpes labial, culebrilla)", en: "Reactivation of latent viruses (cold sores, shingles)" }, { es: "Más infecciones si bajan las defensas", en: "More infections if the defenses drop" }],
    tools: { es: "La NASA no nombra tratamientos; vigila con muestras de sangre, saliva y orina.", en: "NASA does not name treatments; it monitors with blood, saliva and urine samples." },
    self: [
      { es: "No te rasques ni toques la zona.", en: "Do not scratch or touch the area." },
      { es: "Anota dónde, cuándo empezó y cómo es.", en: "Write down where it is, when it started and what it looks like." },
      { es: "Avisa al cirujano de vuelo; da las muestras que te pida.", en: "Tell the flight surgeon; give the samples they ask for." },
      { es: "Cuida tu higiene y descansa: el estrés y el poco sueño empeoran las defensas.", en: "Look after your hygiene and rest: stress and little sleep weaken the defenses." },
    ],
    mate: [
      { es: "Pídele que no se toque la zona.", en: "Ask them not to touch the area." },
      { es: "Evita el contacto directo y no compartáis toallas.", en: "Avoid direct contact and do not share towels." },
      { es: "Avisa al cirujano de vuelo y ayúdale a tomar las muestras.", en: "Tell the flight surgeon and help take the samples." },
      { es: "Anota lo que ves y a qué hora.", en: "Write down what you see and at what time." },
    ],
    pages: [`${PAGE}risk-of-altered-immune-system-responses/`],
  },
  {
    id: "hands",
    label: { es: "Brazos y manos · paseos espaciales", en: "Arms and hands · spacewalks" },
    risks: ["SPACEWALK_INJURY_PERFORMANCE"],
    site: [0.63, -0.3, 0.12],
    tool: "band",
    problems: [{ es: "Lesiones y fatiga durante el paseo espacial", en: "Injuries and fatigue during the spacewalk" }, { es: "Carga física y mental alta con el traje", en: "High physical and mental load in the suit" }, { es: "Descompresión, poco oxígeno o mucho CO2 dentro del traje", en: "Decompression, low oxygen or high CO2 inside the suit" }],
    tools: { es: "Protocolos de respiración de oxígeno previa, trajes rediseñados con monitorización y ejercicio para mantener hueso y músculo.", en: "Pre-breathe oxygen protocols, redesigned suits with monitoring and exercise to maintain bone and muscle." },
    self: [
      { es: "Para la tarea y avisa por radio.", en: "Stop the task and call on the radio." },
      { es: "Vuelve a la esclusa siguiendo el protocolo de emergencia del paseo.", en: "Return to the airlock following the spacewalk emergency protocol." },
      { es: "No fuerces la mano o el brazo dolorido.", en: "Do not strain the sore hand or arm." },
      { es: "Avisa al cirujano de vuelo al volver.", en: "Tell the flight surgeon when you are back." },
    ],
    mate: [
      { es: "Habla con él por radio y pídele que pare.", en: "Talk to them by radio and ask them to stop." },
      { es: "Ayúdale a volver a la esclusa con el protocolo.", en: "Help them return to the airlock following the protocol." },
      { es: "Revisa el traje y sus indicadores antes de abrirlo.", en: "Check the suit and its indicators before opening it." },
      { es: "Avisa al cirujano de vuelo.", en: "Tell the flight surgeon." },
    ],
    pages: [`${PAGE}risk-of-injury-and-compromised-performance-from-extravehicular-activity-eva/`],
  },
  {
    id: "spine",
    label: { es: "Columna y cadera · huesos", en: "Spine and hip · bones" },
    risks: ["BONE_CHANGES"],
    site: [0, -0.3, 0.22],
    tool: "load",
    problems: [{ es: "Pérdida de densidad ósea (de 1 % a 1,5 % al mes en misiones de 4 a 6 meses)", en: "Loss of bone density (1% to 1.5% per month on 4 to 6 month missions)" }, { es: "Más riesgo de fractura", en: "Higher risk of fracture" }, { es: "La columna se alarga", en: "The spine lengthens" }],
    tools: { es: "Ejercicio de resistencia, escáner óseo antes y después del vuelo y medicación (bifosfonatos).", en: "Resistance exercise, a bone scan before and after the flight and medication (bisphosphonates)." },
    self: [
      { es: "Haz tu ejercicio de resistencia cada día.", en: "Do your resistance exercise every day." },
      { es: "Evita golpes y cargas bruscas.", en: "Avoid knocks and sudden loads." },
      { es: "Si notas dolor intenso en la espalda o la cadera, para y avísalo.", en: "If you feel severe pain in your back or hip, stop and report it." },
      { es: "Pide al cirujano de vuelo que revise tu plan de ejercicio.", en: "Ask the flight surgeon to review your exercise plan." },
    ],
    mate: [
      { es: "No lo muevas de golpe si se ha golpeado o le duele la espalda.", en: "Do not move them suddenly if they have been hit or their back hurts." },
      { es: "Sujétalo con suavidad para que no flote.", en: "Hold them gently so they do not float away." },
      { es: "Avisa al cirujano de vuelo.", en: "Tell the flight surgeon." },
      { es: "Sigue sus instrucciones para moverlo.", en: "Follow their instructions on how to move them." },
    ],
    pages: [`${PAGE}risk-of-spaceflight-induced-bone-changes/`],
  },
  {
    id: "legs",
    label: { es: "Piernas · forma física", en: "Legs · fitness" },
    risks: ["CARDIORESPIRATORY_MUSCULOSKELETAL_FITNESS"],
    site: [0.2, -1.0, 0.1],
    tool: "band",
    problems: [{ es: "Menos fuerza, resistencia y agilidad (de 10 % a 12 % de media)", en: "Less strength, endurance and agility (10% to 12% on average)" }, { es: "Más riesgo de caídas y lesiones al volver a la gravedad", en: "Higher risk of falls and injuries on return to gravity" }],
    tools: { es: "Ejercicio de resistencia y aeróbico (en la ISS, de 6 a 7 días por semana, 1,5 horas al día) y autoevaluaciones periódicas de forma física.", en: "Resistance and aerobic exercise (on the ISS, 6 to 7 days a week, 1.5 hours a day) and periodic fitness self-assessments." },
    self: [
      { es: "Haz tu sesión de ejercicio completa, aunque no te apetezca.", en: "Do your full exercise session, even if you do not feel like it." },
      { es: "Alterna fuerza y ejercicio aeróbico.", en: "Alternate strength and aerobic exercise." },
      { es: "Haz tu autoevaluación de forma física cuando toque.", en: "Do your fitness self-assessment when it is due." },
      { es: "Avisa si algo te duele al hacerlo.", en: "Say so if anything hurts while you do it." },
    ],
    mate: [
      { es: "Anímalo a entrenar y entrenad juntos.", en: "Encourage them to train and train together." },
      { es: "Ayúdale a sujetarse bien en la máquina.", en: "Help them secure themselves properly on the machine." },
      { es: "Si se lesiona, avisa al cirujano de vuelo.", en: "If they get hurt, tell the flight surgeon." },
      { es: "Apunta su progreso para su autoevaluación.", en: "Note their progress for their self-assessment." },
    ],
    pages: [`${PAGE}risk-of-reduced-cardiorespiratory-and-musculoskeletal-fitness/`],
  },
];
