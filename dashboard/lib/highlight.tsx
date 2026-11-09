import type { ReactNode } from "react";

// Transcript highlighting: quantities, rates and units in brass, item names underlined.
// Prisma's codemix output writes Hindi in Devanagari and English in Latin, so both are listed.
// Presentation only: nothing here feeds extraction.

const NUMBER_WORDS = new Set(
  [
    // Hindi
    "एक", "दो", "तीन", "चार", "पाँच", "पांच", "छह", "छः", "छे", "सात", "आठ", "नौ", "दस", "ग्यारह", "बारह",
    "तेरह", "चौदह", "पंद्रह", "पन्द्रह", "सोलह", "सत्रह", "अठारह", "उन्नीस", "बीस", "पच्चीस", "तीस", "पैंतीस",
    "चालीस", "बयालीस", "पैंतालीस", "पचास", "बावन", "पचपन", "साठ", "बासठ", "छियासठ", "सत्तर", "पचहत्तर",
    "अस्सी", "नब्बे", "पचानवे", "पंचानवे", "सौ", "हज़ार", "हजार", "लाख", "डेढ़", "ढाई", "साढ़े", "सवा", "पौने",
    // English
    "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
    "fifteen", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety", "hundred",
    "thousand", "lakh", "half",
  ].map((w) => w.toLowerCase()),
);

/** Number words that are also common verbs or articles ("कर दो", "एक नया order"). */
const AMBIGUOUS = new Set(["दो", "एक", "one", "two"]);

const UNITS = new Set(
  ["kg", "kilo", "किलो", "mm", "एमएम", "piece", "pieces", "pcs", "पीस", "रुपये", "रुपए", "rupees", "rupaye",
    "inch", "इंच", "ton", "टन", "meter", "मीटर", "feet", "फीट"].map((w) => w.toLowerCase()),
);

const ITEMS = new Set(
  ["bracket", "brackets", "sheet", "sheets", "angle", "angles", "channel", "channels", "flange", "flanges",
    "plate", "plates", "base", "pipe", "pipes", "rod", "rods", "bar", "bars", "beam", "beams", "ms", "ismc",
    "ब्रैकेट", "ब्रेकेट", "शीट", "एंगल", "चैनल", "फ्लैंज", "फ्लेंज", "प्लेट", "पाइप", "रॉड", "बार"].map((w) =>
    w.toLowerCase(),
  ),
);

type Kind = "num" | "unit" | "item" | null;
interface Tok {
  text: string;
  kind: Kind;
  word: boolean;
}

const WORD = /([\p{L}\p{M}\p{N}₹][\p{L}\p{M}\p{N}.,₹]*[\p{L}\p{M}\p{N}]|[\p{L}\p{M}\p{N}₹])/u;

function classify(word: string): Kind {
  const w = word.toLowerCase();
  if (/^₹?\d[\d,]*(\.\d+)?$/.test(w) || /^\d+(mm|kg)$/.test(w)) return "num";
  if (NUMBER_WORDS.has(w)) return "num";
  if (UNITS.has(w)) return "unit";
  if (ITEMS.has(w)) return "item";
  return null;
}

function tokenize(text: string): Tok[] {
  // split() with a capture group alternates separator, word, separator, word, ...
  return text
    .split(new RegExp(WORD.source, "gu"))
    .map((t, i): Tok => (i % 2 ? { text: t, kind: classify(t), word: true } : { text: t, kind: null, word: false }))
    .filter((t) => t.text !== "");
}

const isSpace = (t: Tok | undefined) => !!t && !t.word && /^\s+$/.test(t.text);

/** Keep a number run only if it clearly is a number: has a digit, several words, or a unit/item after it. */
function resolveNumbers(toks: Tok[]): void {
  for (let i = 0; i < toks.length; i++) {
    if (toks[i].kind !== "num") continue;
    const run = [i];
    let j = i;
    while (isSpace(toks[j + 1]) && toks[j + 2]?.kind === "num") {
      j += 2;
      run.push(j);
    }
    const next = isSpace(toks[j + 1]) ? toks[j + 2] : undefined;
    const sure =
      run.length > 1 ||
      /\d/.test(toks[i].text) ||
      !AMBIGUOUS.has(toks[i].text.toLowerCase()) ||
      next?.kind === "unit" ||
      next?.kind === "item";
    if (!sure) for (const k of run) toks[k].kind = null;
    i = j;
  }
  // A unit only counts right after a number ("तीन सौ किलो"), so "piece" alone stays plain.
  for (let i = 0; i < toks.length; i++) {
    if (toks[i].kind === "unit") {
      const prev = isSpace(toks[i - 1]) ? toks[i - 2] : toks[i - 1];
      toks[i].kind = prev?.kind === "num" ? "num" : null;
    }
  }
}

const STYLE: Record<"num" | "item", string> = {
  num: "rounded-sm bg-transparent font-semibold text-accent",
  item: "bg-transparent font-medium text-ink underline decoration-accent/45 decoration-2 underline-offset-[5px]",
};

/** Transcript text with numbers and item names marked up. */
export function Highlight({ text }: { text: string }): ReactNode {
  const toks = tokenize(text);
  resolveNumbers(toks);

  const out: ReactNode[] = [];
  let i = 0;
  while (i < toks.length) {
    const kind = toks[i].kind;
    if (kind !== "num" && kind !== "item") {
      out.push(toks[i].text);
      i++;
      continue;
    }
    // Merge "तीन सौ किलो" or "MS sheet" into one mark.
    let j = i;
    while (isSpace(toks[j + 1]) && toks[j + 2]?.kind === kind) j += 2;
    out.push(
      <mark key={i} className={STYLE[kind]}>
        {toks
          .slice(i, j + 1)
          .map((t) => t.text)
          .join("")}
      </mark>,
    );
    i = j + 1;
  }
  return <>{out}</>;
}
