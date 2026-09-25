/** Where the Streamlit dashboard lives. Overridable at build time. */
export const DASHBOARD_URL =
  import.meta.env.VITE_DASHBOARD_URL ?? "http://localhost:8501"

/**
 * Mission facts, taken from the KJS-SRS-01 use-case document so the copy and
 * the source stay in step. Kept in one place.
 */
export const MISSION = {
  college: "K J Somaiya School of Engineering",
  course: "DBMS Mini Project · SY B.Tech IT",
  useCase: "KJS-SRS-01",
  useCaseTitle:
    "SomaiyaSat & SomaiyaPod: A PocketQube Mission featuring Autonomous " +
    "AI-Based Inter-Satellite Data Routing and Advanced Multi-Mode Amateur " +
    "Radio Payloads (M17, Codec2, SSTV & TT&C / Housekeeping)",
  vertical: "Space Technology and Remote Sensing",
  collaborator: "ReOrbit, Finland",
  beneficiaries: "Global amateur radio (HAM) community",
  faculty: [
    {
      name: "Dr. Umesh Shinde",
      role: "Associate Professor, Basic Science & Humanities",
      institute: "K J Somaiya Institute of Technology",
    },
    {
      name: "Dr. Shailesh Nikam",
      role: "Professor, Mechanical Engineering",
      institute: "K J Somaiya School of Engineering",
    },
  ],
} as const

/**
 * SomaiyaSat's actual envelope, from Fig. 2 of the use-case document.
 * It is NOT a 50 mm cube — that is the generic 1P PocketQube unit the
 * background section refers to. This spacecraft is an elongated stack.
 */
export const SAT_DIMENSIONS = {
  length: 127.4, // (l) length of PocketQube
  width: 57.9, // (c) width of PocketQube
  height: 57.2, // (a) height with solar panels
  pcbThickness: 1.6, // (b)
  solarCell: { length: 42.25, width: 22.95 }, // (m), (j)
  standoffWidth: 5.3, // (n)
} as const
