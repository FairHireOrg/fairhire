import type { ResumeDoc, Scored } from "./types";

/** A fixed sample used by the landing page's product shot. Never sent anywhere. */
export const DEMO_DOC: ResumeDoc = {
  contact: {
    name: "Jordan Lee", headline: "Backend Engineer", email: "jordan.lee@example.com", phone: "(415) 555-0142",
    location: "San Francisco, CA", links: ["linkedin.com/in/jordanlee"], other: [],
  },
  summary: "Backend engineer with six years building data pipelines and APIs for healthcare analytics. Focused on reliable, well-tested systems that scale.",
  sections: [
    {
      id: "demo-exp", kind: "experience", title: "Work experience", groups: [],
      entries: [
        {
          id: "demo-e1", heading: "Senior Backend Engineer", subheading: "Northwind Health", location: "", start: "Jan 2022", end: "Present",
          link: "", detail: "",
          bullets: [
            "Led migration of claims ingestion to an event-driven architecture, reducing processing delay from hours to minutes",
            "Designed REST and gRPC APIs consumed by five internal analytics teams",
          ],
        },
        {
          id: "demo-e2", heading: "Data Engineer", subheading: "Brightline Labs", location: "", start: "Jun 2019", end: "12/2021",
          link: "", detail: "",
          bullets: [
            "Built Airflow pipelines processing 40M claims records per day",
            "Cut warehouse query latency 62% by redesigning partition strategy",
            "Mentored three junior engineers through onboarding",
          ],
        },
      ],
    },
    {
      id: "demo-edu", kind: "education", title: "Education", groups: [],
      entries: [{
        id: "demo-d1", heading: "B.S. Computer Science", subheading: "University of Washington", location: "", start: "2015", end: "2019",
        link: "", detail: "", bullets: [""],
      }],
    },
    {
      id: "demo-skills", kind: "skills", title: "Skills", entries: [],
      groups: [
        { label: "Languages", items: ["Python", "Go", "SQL", "TypeScript"] },
        { label: "Tools", items: ["Airflow", "dbt", "Postgres", "Kafka", "Docker", "Terraform"] },
      ],
    },
  ],
};

const target = { section: "demo-exp", entry: "demo-e2" };
export const DEMO_SCORED: Scored = {
  document: DEMO_DOC,
  text: "",
  owners: [],
  ruleset: "demo",
  ats: {
    score: 84, grade: "Good", dimensions: [],
    recommendations: [
      {
        severity: "medium", code: "dates", title: "Dates use mixed formats",
        detail: "“Jun 2019 – 12/2021” mixes a month name with a numeric date.", action: "Use one format throughout.",
        start: 0, end: 0, line: -1, target,
      },
      {
        severity: "high", code: "phone", title: "Phone number not found in text",
        detail: "It may be in a header or an image.", action: "Add it to the contact line at the top.",
        start: 0, end: 0, line: -1, target: { section: "contact", entry: "" },
      },
      {
        severity: "low", code: "heading", title: "Section “My Journey”",
        detail: "Parsers look for standard section names.", action: "Rename to “Experience”.",
        start: 0, end: 0, line: -1, target: { section: "demo-exp", entry: "" },
      },
    ],
  },
};
