import type { V3 } from "./mannequin";
import hrp from "../../../../shared/hrp.json";

/**
 * The SALUD tab: nine points on the body, each tied to the official HRP "Risks Involving Human Physiology" it
 * covers (https://www.nasa.gov/hrp/risks/, pages read 2026-11-14). `problems` and `tools` only repeat what those
 * pages say (a tool is listed only when a page names it, otherwise `tools` says so); `self` and `mate` are PULSAR's
 * own wording (team assumption): generic first steps that always end in "tell the flight surgeon". Not clinical
 * guidance and not a medical device. PULSAR never judges any of this: none of it is measured.
 */
export type HealthTool = "arrows" | "probe" | "oxygen" | "pack" | "swab" | "band" | "load";

export type HealthPoint = {
  id: string;
  label: string;
  /** Ids in shared/hrp.json; the panel shows their official names. */
  risks: (keyof typeof hrp.risks)[];
  /** Where it sits on the standing figure (front view, so only x and y place the marker). */
  site: V3;
  /** The 3D picture: which tool the animation shows working on that zone. */
  tool: HealthTool;
  problems: string[];
  tools: string;
  self: string[];
  mate: string[];
  /** Detail pages of the risks, in the order of `risks`. */
  pages: string[];
};

const PAGE = "https://www.nasa.gov/reference/";

export const HEALTH_POINTS: HealthPoint[] = [
  {
    id: "head",
    label: "Cabeza · equilibrio",
    risks: ["SENSORIMOTOR_VESTIBULAR"],
    site: [0, 1.66, 0.2],
    tool: "arrows",
    problems: ["Mareo y náuseas por el movimiento", "Desorientación y pérdida de equilibrio", "Torpeza entre la mano y el ojo; cuesta manejar mandos"],
    tools: "La NASA no tiene aún una contramedida establecida: investiga medicación contra el mareo, entrenamiento y ayudas de orientación.",
    self: [
      "Detén lo que haces y sujétate a un punto fijo.",
      "Fija la vista en un punto estable y mueve la cabeza despacio.",
      "No uses mandos ni hagas tareas críticas hasta que pase.",
      "Avisa a la tripulación y al cirujano de vuelo; toma medicación solo si él te lo indica.",
    ],
    mate: [
      "Sujétalo para que no flote ni se golpee.",
      "Háblale despacio y pregúntale cómo se siente.",
      "Aléjalo de los mandos y de las tareas críticas.",
      "Avisa al cirujano de vuelo y sigue sus instrucciones.",
    ],
    pages: [`${PAGE}risk-of-altered-sensorimotor-and-vestibular-function/`],
  },
  {
    id: "eyes",
    label: "Ojos · visión",
    risks: ["SANS"],
    site: [-0.24, 1.42, 0.2],
    tool: "probe",
    problems: ["Cambios en la visión", "Hinchazón del nervio óptico y pliegues en la retina", "Más probable en misiones largas"],
    tools: "No hay contramedida probada. Se usa un fundoscopio para ver la retina; se investigan suplementos y formas mecánicas de revertir el desplazamiento de líquidos hacia la cabeza.",
    self: [
      "Anota cuándo notas un cambio en la visión y cómo es.",
      "No te frotes los ojos.",
      "Avisa al cirujano de vuelo y pide el examen de retina con el fundoscopio.",
      "Evita tareas que exijan vista fina hasta que te revisen.",
    ],
    mate: [
      "Pregúntale qué ve distinto y desde cuándo.",
      "Pídele que no se frote los ojos.",
      "Avisa al cirujano de vuelo; ayúdale a preparar el fundoscopio si te lo piden.",
      "Quédate con él si ha de hacer tareas delicadas.",
    ],
    pages: [`${PAGE}risk-of-spaceflight-associated-neuro-ocular-syndrome-sans/`],
  },
  {
    id: "heart",
    label: "Corazón · circulación",
    risks: ["CARDIOVASCULAR_ADAPTATIONS"],
    site: [0.16, 0.72, 0.25],
    tool: "probe",
    problems: ["Latido irregular (arritmia)", "Coágulos de sangre", "Presión baja y riesgo de desmayo al volver a la gravedad"],
    tools: "Ejercicio regular, dieta sana, prendas de compresión en las piernas, beber mucho líquido antes de aterrizar y un ecógrafo para ver el corazón.",
    self: [
      "Detente y sujétate en una posición segura.",
      "Cuenta tu pulso en la muñeca (mira la pestaña MEDIR).",
      "Avisa a la tripulación; si hay dolor en el pecho o te desmayas, avisa de inmediato al cirujano de vuelo.",
      "Si el cirujano lo pide, usa el ecógrafo para que vea tu corazón.",
    ],
    mate: [
      "Comprueba si responde y si respira.",
      "Busca el pulso en su muñeca (pestaña MEDIR).",
      "Avisa ya al cirujano de vuelo y a la tripulación.",
      "Si no respira, sigue el protocolo de reanimación que te indique el cirujano de vuelo.",
    ],
    pages: [`${PAGE}risk-of-cardiovascular-adaptations/`],
  },
  {
    id: "lungs",
    label: "Pulmones · oxígeno y presión",
    risks: ["HYPOXIA", "DECOMPRESSION_SICKNESS"],
    site: [-0.2, 0.58, 0.25],
    tool: "oxygen",
    problems: ["Confusión, dolor de cabeza y visión alterada (poco oxígeno)", "Dificultad para dormir", "Dolor intenso y dificultad para respirar tras pasar a menor presión (descompresión)"],
    tools: "Protocolos que equilibran oxígeno y presión, respirar oxígeno puro antes de un paseo espacial y el protocolo para terminar el paseo y volver a la nave deprisa pero con seguridad.",
    self: [
      "Detén el esfuerzo y avisa a la tripulación.",
      "Vuelve a una zona con presión y oxígeno normales siguiendo el protocolo.",
      "Usa el oxígeno de la nave si el procedimiento lo indica.",
      "Avisa al cirujano de vuelo y anota qué sentías y cuándo empezó.",
    ],
    mate: [
      "Ponlo a salvo en una zona con presión y oxígeno normales.",
      "Dale el oxígeno si el procedimiento o el cirujano lo indican.",
      "Si hizo un paseo espacial, díselo al cirujano de vuelo.",
      "Quédate con él y sigue las instrucciones del cirujano de vuelo.",
    ],
    pages: [`${PAGE}risk-of-hypoxia/`, `${PAGE}risk-of-decompression-sickness/`],
  },
  {
    id: "gut",
    label: "Abdomen · comida y microbios",
    risks: ["FOOD_AND_NUTRITION", "HOST_MICROORGANISM"],
    site: [0, 0.1, 0.25],
    tool: "pack",
    problems: ["Comer poco o siempre lo mismo", "Cambios en los microbios del intestino y de la piel", "Más riesgo de enfermar"],
    tools: "Un sistema de comida mejorado (más variedad, menos sodio; más de 200 alimentos y bebidas en la ISS) y muestras biológicas y de superficies para vigilar los microbios.",
    self: [
      "Come lo planificado y varía el menú.",
      "Si pierdes el apetito o te duele el abdomen, anótalo.",
      "Lávate las manos o usa toallitas antes de comer.",
      "Avisa al cirujano de vuelo si dura más de un día.",
    ],
    mate: [
      "Pregúntale qué ha comido y cómo se siente.",
      "Ayúdale a preparar comida que le apetezca.",
      "Evita compartir utensilios si está enfermo.",
      "Avisa al cirujano de vuelo si no mejora.",
    ],
    pages: [`${PAGE}risk-of-inadequate-food-and-nutrition/`, `${PAGE}risk-of-host-microorganism-interactions/`],
  },
  {
    id: "skin",
    label: "Piel · defensas",
    risks: ["ALTERED_IMMUNE_RESPONSE"],
    site: [-0.56, 0.4, 0.1],
    tool: "swab",
    problems: ["Erupciones y alergias poco habituales", "Reactivación de virus latentes (herpes labial, culebrilla)", "Más infecciones si bajan las defensas"],
    tools: "La NASA no nombra tratamientos; vigila con muestras de sangre, saliva y orina.",
    self: [
      "No te rasques ni toques la zona.",
      "Anota dónde, cuándo empezó y cómo es.",
      "Avisa al cirujano de vuelo; da las muestras que te pida.",
      "Cuida tu higiene y descansa: el estrés y el poco sueño empeoran las defensas.",
    ],
    mate: [
      "Pídele que no se toque la zona.",
      "Evita el contacto directo y no compartáis toallas.",
      "Avisa al cirujano de vuelo y ayúdale a tomar las muestras.",
      "Anota lo que ves y a qué hora.",
    ],
    pages: [`${PAGE}risk-of-altered-immune-system-responses/`],
  },
  {
    id: "hands",
    label: "Brazos y manos · paseos espaciales",
    risks: ["SPACEWALK_INJURY_PERFORMANCE"],
    site: [0.63, -0.3, 0.12],
    tool: "band",
    problems: ["Lesiones y fatiga durante el paseo espacial", "Carga física y mental alta con el traje", "Descompresión, poco oxígeno o mucho CO2 dentro del traje"],
    tools: "Protocolos de respiración de oxígeno previa, trajes rediseñados con monitorización y ejercicio para mantener hueso y músculo.",
    self: [
      "Para la tarea y avisa por radio.",
      "Vuelve a la esclusa siguiendo el protocolo de emergencia del paseo.",
      "No fuerces la mano o el brazo dolorido.",
      "Avisa al cirujano de vuelo al volver.",
    ],
    mate: [
      "Habla con él por radio y pídele que pare.",
      "Ayúdale a volver a la esclusa con el protocolo.",
      "Revisa el traje y sus indicadores antes de abrirlo.",
      "Avisa al cirujano de vuelo.",
    ],
    pages: [`${PAGE}risk-of-injury-and-compromised-performance-from-extravehicular-activity-eva/`],
  },
  {
    id: "spine",
    label: "Columna y cadera · huesos",
    risks: ["BONE_CHANGES"],
    site: [0, -0.3, 0.22],
    tool: "load",
    problems: ["Pérdida de densidad ósea (de 1 % a 1,5 % al mes en misiones de 4 a 6 meses)", "Más riesgo de fractura", "La columna se alarga"],
    tools: "Ejercicio de resistencia, escáner óseo antes y después del vuelo y medicación (bifosfonatos).",
    self: [
      "Haz tu ejercicio de resistencia cada día.",
      "Evita golpes y cargas bruscas.",
      "Si notas dolor intenso en la espalda o la cadera, para y avísalo.",
      "Pide al cirujano de vuelo que revise tu plan de ejercicio.",
    ],
    mate: [
      "No lo muevas de golpe si se ha golpeado o le duele la espalda.",
      "Sujétalo con suavidad para que no flote.",
      "Avisa al cirujano de vuelo.",
      "Sigue sus instrucciones para moverlo.",
    ],
    pages: [`${PAGE}risk-of-spaceflight-induced-bone-changes/`],
  },
  {
    id: "legs",
    label: "Piernas · forma física",
    risks: ["CARDIORESPIRATORY_MUSCULOSKELETAL_FITNESS"],
    site: [0.2, -1.0, 0.1],
    tool: "band",
    problems: ["Menos fuerza, resistencia y agilidad (de 10 % a 12 % de media)", "Más riesgo de caídas y lesiones al volver a la gravedad"],
    tools: "Ejercicio de resistencia y aeróbico (en la ISS, de 6 a 7 días por semana, 1,5 horas al día) y autoevaluaciones periódicas de forma física.",
    self: [
      "Haz tu sesión de ejercicio completa, aunque no te apetezca.",
      "Alterna fuerza y ejercicio aeróbico.",
      "Haz tu autoevaluación de forma física cuando toque.",
      "Avisa si algo te duele al hacerlo.",
    ],
    mate: [
      "Anímalo a entrenar y entrenad juntos.",
      "Ayúdale a sujetarse bien en la máquina.",
      "Si se lesiona, avisa al cirujano de vuelo.",
      "Apunta su progreso para su autoevaluación.",
    ],
    pages: [`${PAGE}risk-of-reduced-cardiorespiratory-and-musculoskeletal-fitness/`],
  },
];
