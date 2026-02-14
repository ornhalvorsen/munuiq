/** Trigger configuration — defines a mention trigger like @ or $ */
export interface MentionTriggerConfig {
  char: string;       // "@" or "$"
  label: string;      // "Location" or "Product"
  color: string;      // Tailwind color key: "blue" or "amber"
  entityType: string; // Key into entities map: "location" or "product"
}

/** A single pickable entity */
export interface MentionEntity {
  id: string;
  label: string;
  description?: string;
  type: string; // "location" or "product"
}

/** A resolved mention in the input */
export interface Mention {
  entity: MentionEntity;
  trigger: MentionTriggerConfig;
}

/** Content model — the input is a list of segments */
export type Segment =
  | { kind: "text"; text: string }
  | { kind: "mention"; mention: Mention };

/** Autocomplete state exposed by the hook */
export interface AutocompleteState {
  active: boolean;
  trigger: MentionTriggerConfig | null;
  query: string;
  results: MentionEntity[];
  highlightIndex: number;
}

/** Data sent on form submit */
export interface MentionSubmitData {
  plainText: string;
  mentions: Array<{ type: string; id: string; label: string }>;
}
