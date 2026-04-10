import { generateDummyPassword } from "./db/utils";

export const isProductionEnvironment = process.env.NODE_ENV === "production";
export const isDevelopmentEnvironment = process.env.NODE_ENV === "development";
export const isTestEnvironment = Boolean(
  process.env.PLAYWRIGHT_TEST_BASE_URL ||
    process.env.PLAYWRIGHT ||
    process.env.CI_PLAYWRIGHT
);

export const guestRegex = /^guest-\d+$/;

export const DUMMY_PASSWORD = generateDummyPassword();

export const suggestions = [
  "Wat is borstkanker en hoe wordt het vastgesteld?",
  "Wat zijn de behandelmogelijkheden bij darmkanker?",
  "Hoe kan ik omgaan met vermoeidheid tijdens chemotherapie?",
  "Wat zijn de overlevingscijfers voor longkanker in Nederland?",
];
