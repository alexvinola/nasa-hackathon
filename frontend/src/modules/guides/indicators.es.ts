/** Spanish text of the indicator guides in shared/indicators.json (English, protected), by signal. Steps keep the JSON's order and focus. */
export type GuideEs = { label: string; instrument: string; how: string[]; why: string; whenAbnormal: string };

export const INDICATORS_ES: Record<string, GuideEs> = {
  "biometrics.heartRateBpm": {
    label: "Frecuencia cardíaca",
    instrument: "Dos dedos y un cronómetro",
    how: [
      "Para una lectura en reposo, descansa antes al menos 10 minutos.",
      "Gira una mano con la palma hacia arriba y busca la parte interior de la muñeca, justo debajo de la base del pulgar.",
      "Apoya ahí las yemas de los dedos índice y medio. No uses el pulgar.",
      "Presiona con suavidad con las yemas planas hasta notar el pulso.",
      "Cuenta los latidos durante 30 segundos y multiplica por 2, o cuéntalos durante un minuto completo.",
    ],
    why: "El pulso es la señal más sencilla de cómo se las arregla el corazón. La NASA vigila el Risk of Cardiovascular Adaptations en el vuelo espacial, y lejos de la Tierra un pulso que cuentas tú mismo es lo primero que te pedirá el médico de la tripulación.",
    whenAbnormal: "PULSAR todavía no juzga este valor: avisa al médico de la tripulación. Dale el número, cuándo lo tomaste y cómo te sientes; no decidas por tu cuenta si es normal.",
  },
  "selfReport.bloodPressure": {
    label: "Presión arterial",
    instrument: "Manguito automático de brazo",
    how: [
      "No comas ni bebas durante los 30 minutos previos, y vacía la vejiga.",
      "Siéntate con la espalda apoyada al menos 5 minutos, con los pies planos y las piernas sin cruzar.",
      "Colócate el manguito en la parte superior del brazo desnudo, ajustado pero cómodo.",
      "Apoya el brazo de modo que el manguito quede a la altura del pecho.",
      "Pon en marcha el monitor y no hables mientras mide.",
      "Toma al menos dos lecturas, con 1 a 2 minutos de diferencia, y anota cada una.",
    ],
    why: "La presión arterial muestra cómo se adaptan el corazón y los vasos sanguíneos. Es una de las lecturas detrás del Risk of Cardiovascular Adaptations de la NASA, y un registro cuidadoso permite al cirujano de vuelo ver una tendencia en lugar de un solo número.",
    whenAbnormal: "PULSAR todavía no juzga este valor: avisa al médico de la tripulación. Dale los dos números, cuándo los tomaste y cómo te sientes; no decidas por tu cuenta si son normales.",
  },
  "selfReport.glucoseMgDl": {
    label: "Glucosa en sangre",
    instrument: "Glucómetro, tira reactiva y lanceta",
    how: [
      "Deja a mano el glucómetro, una tira reactiva y el dispositivo de la lanceta antes de empezar.",
      "Lávate la yema del dedo con agua y jabón, no con una toallita de alcohol, y deja que se seque por completo.",
      "Carga una lanceta en su dispositivo con resorte y pínchate el dedo.",
      "Coloca una gota de sangre en la tira reactiva.",
      "Lee el número en la pantalla del glucómetro. Si es inesperado, repite con una tira nueva.",
      "Anota el resultado con la hora del día.",
    ],
    why: "La glucosa en sangre refleja lo bien que la comida alimenta al cuerpo. La NASA vigila el Risk of Inadequate Food and Nutrition en misiones largas, donde el menú es fijo y el reabastecimiento queda lejos.",
    whenAbnormal: "PULSAR todavía no juzga este valor: avisa al médico de la tripulación. Dale el número, cuándo lo tomaste y cuándo comiste por última vez; no decidas por tu cuenta si es normal.",
  },
  "selfReport.bodyTempC": {
    label: "Temperatura corporal",
    instrument: "Termómetro electrónico, en la boca",
    how: [
      "Espera de 20 a 30 minutos después de comer o beber algo caliente o frío, y 1 hora después de un ejercicio intenso.",
      "Limpia el termómetro.",
      "Coloca la punta debajo de la lengua y cierra los labios.",
      "Respira por la nariz y sujeta el termómetro con firmeza con los labios.",
      "Déjalo en su sitio hasta que pite y luego lee la pantalla.",
      "Vuelve a limpiar el termómetro.",
    ],
    why: "Un cambio en la temperatura corporal puede ser una señal temprana de que el cuerpo está combatiendo algo. La NASA vigila el Risk of Altered Immune System Responses en el vuelo espacial, y en una cabina cerrada una enfermedad importa a toda la tripulación.",
    whenAbnormal: "PULSAR todavía no juzga este valor: avisa al médico de la tripulación. Dale el número, cuándo lo tomaste y cómo te sientes; no decidas por tu cuenta si es normal.",
  },
  "selfReport.sleepHoursLast24h": {
    label: "Sueño",
    instrument: "Tu propio registro de sueño",
    how: [
      "Repasa las últimas 24 horas, contando desde ahora.",
      "Suma cada periodo que dormiste de verdad, siestas incluidas. No cuentes el tiempo que pasaste despierto en la cama.",
      "Introduce el total de horas en PULSAR.",
    ],
    why: "La NASA informa de que los astronautas suelen sufrir falta de sueño, y la fatiga provoca errores en las tareas. Es el Risk of Inadequate Sleep and Irregular Schedules, y un registro de sueño honesto es la forma en que la tripulación lo detecta pronto.",
    whenAbnormal: "El motor de reglas comprueba este valor. Si levanta una alerta, sigue los pasos de la contramedida que muestra PULSAR y avisa a un compañero antes del trabajo crítico.",
  },
  "selfReport.mood": {
    label: "Estado de ánimo",
    instrument: "Una autoevaluación diaria, de 1 a 5",
    how: [
      "Tómate un momento de calma y pregúntate cómo te sientes en general ahora mismo.",
      "Elige un número de 1 (muy bajo) a 5 (muy bueno). No hay respuesta correcta.",
      "Introdúcelo en PULSAR como el ánimo de hoy.",
    ],
    why: "Los meses de Isolation and Confinement desgastan a cualquiera. La NASA vigila el Risk of Behavioral Changes and Psychiatric Disorders, y una breve autoevaluación diaria te permite a ti y a la tripulación notar una caída antes de que afecte a la misión.",
    whenAbnormal: "El motor de reglas comprueba este valor. Si levanta una alerta, sigue los pasos de la contramedida que muestra PULSAR y habla con un compañero de confianza.",
  },
};
