/**
 * Disclosures shown at all times, even before the backend answers. Wording matches the backend
 * (apps/web_api/config.py and sentinel/presentation/labels.py) and the M5 claims registry.
 */
import type { Disclosures } from "./protocol";

export const DEFAULT_DISCLOSURES: Disclosures = {
  digital_label: "SIMULATED DIGITAL CHANNEL",
  digital_note: "Local simulator — not a production checkpoint integration.",
  digital_long:
    "The digital channel is a local simulator used to demonstrate cross-channel conformance logic. " +
    "It is not an integration with a production checkpoint system. Field accuracy is not established.",
  privacy: "Temporary tracking only • No face recognition • No persistent identity",
  frames: "Sampled camera frames are sent to the local MADQAQ analysis backend while the web demo is active.",
  frames_storage: "Frames are analysed in memory and are not saved.",
};

export const PROTOTYPE_NOTE = "Research prototype · local finalist demonstration · not a deployed system";
