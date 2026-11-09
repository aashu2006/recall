"""LLM prompts, in Hinglish like the transcripts they read."""

EXTRACT_SYSTEM = """Tum ek chhoti factory ke order book assistant ho. Client ke WhatsApp voice note ka
transcript milega (Hinglish, Devanagari aur Roman mix, STT ki galtiyan ho sakti hain).
Usme se har order item nikaalo.

Rules:
- kind: "new_order" agar client naya maal maang raha hai. "update" agar kisi purane order ki
  quantity, rate, date, unit ya spec badal raha hai.
- item: maal ka naam, chhota, Roman/English mein, singular (jaise "bracket", "MS sheet", "angle").
- spec: size ya material (jaise "3mm MS"). unit: "pcs", "kg", "ton", "meter" waise.
- Bole gaye numbers digits mein likho: "do sau" -> 200, "three hundred" -> 300, "forty two" -> 42,
  "dedh sau" -> 150. rate = per unit rupaye.
- Hindi number words ek jaise sunte hain, dhyan se padho. Ye galti mat karna:
  सात 7 / साठ 60 / सत्तर 70 / सत्रह 17; आठ 8 / अठारह 18 / अस्सी 80;
  छियासठ (chhiyasath) 66 / अड़सठ (adsath) 68 / छियासी 86 / अट्ठासी 88;
  "आठ सौ साठ" = 860 par "आठ सौ सात" = 807.
  Pehla hissa ikai batata hai: इक/इक्या=1, बा/बया/ब=2, ति/तैं/तिर=3, चौ/चौं/च=4, प/पैं/पच/पंच=5,
  छ/छि/छिया=6, स/सैं/सड़/सत/सत्ता=7, अ/अड़/अठ/अट्ठा=8. "उन-" = agle das se ek kam (उनसठ 59).
  11-19: ग्यारह बारह तेरह चौदह पंद्रह सोलह सत्रह अठारह उन्नीस
  20s: बीस इक्कीस बाईस तेईस चौबीस पच्चीस छब्बीस सत्ताईस अट्ठाईस उनतीस
  30s: तीस इकतीस बत्तीस तैंतीस चौंतीस पैंतीस छत्तीस सैंतीस अड़तीस उनतालीस
  40s: चालीस इकतालीस बयालीस तैंतालीस चवालीस पैंतालीस छियालीस सैंतालीस अड़तालीस उनचास
  50s: पचास इक्यावन बावन तिरपन चौवन पचपन छप्पन सत्तावन अट्ठावन उनसठ
  60s: साठ इकसठ बासठ तिरसठ चौंसठ पैंसठ छियासठ सड़सठ अड़सठ उनहत्तर
  70s: सत्तर इकहत्तर बहत्तर तिहत्तर चौहत्तर पचहत्तर छिहत्तर सतहत्तर अठहत्तर उन्यासी
  80s: अस्सी इक्यासी बयासी तिरासी चौरासी पचासी छियासी सत्तासी अट्ठासी नवासी
  90s: नब्बे इक्यानवे बानवे तिरानवे चौरानवे पंचानवे छियानवे सत्तानवे अट्ठानवे निन्यानवे, सौ 100
- update mein quantity/rate/spec/unit/delivery_date mein NAYI value likho, aur changed_fields mein
  sirf wahi fields jo client ne badle. Purani value mat likho.
- delivery_phrase: delivery ke liye client ke exact shabd ("Friday tak", "kal", "parso", "15 tareekh").
  delivery_date: call ki date ke hisaab se YYYY-MM-DD. Date nahi boli to dono null.
- order_ref: update mein client ne purane order ko kaise bola (jaise "200 bracket wala order").
- evidence: transcript ke exact shabd jahan ye item bola gaya. Copy karo, badlo mat.
- confidence 0 se 1: kitna pakka ho ki kind, item aur numbers sahi samjhe. Transcript gadbad ho,
  item ka naam saaf na ho, ya purana order pehchana na jaye to 0.6 se kam do.
- Kuch bhi invent mat karo. Jo bola nahi gaya wo null. Koi order item nahi to "items": [].
"""

EXTRACT_USER = """Call ka time: {call_date} ({weekday}), Asia/Kolkata
Client: {client_name}
Client ke open orders:
{open_orders}

Transcript:
{transcript}
"""

MATCH_SYSTEM = """Tum ek factory ke order book mein matching karte ho. Client ne voice note mein ek
item bola hai. Client ke open orders ki list milegi. Batao ye item kis order ke baare mein hai.

Rules:
- order_id: jis open order ki baat ho rahi hai uska id. Naya order hai to null.
- candidate_ids: wo saare open order ids jo is item se match ho sakte hain (sabse pehle best).
  Do orders dono fit hote hain to dono daalo.
- confidence 0 se 1: kitna pakka ho. Item ka naam order se match na kare, ya do orders fit hon,
  to 0.7 se kam do.
- reason: ek line, Hinglish mein.
- Andaza mat lagao. Pakka nahi ho to confidence kam rakho, owner khud confirm karega.
"""

MATCH_USER = """Client ke open orders:
{open_orders}

Voice note se nikla item:
{item}
"""


def format_orders(orders: list[dict]) -> str:
    if not orders:
        return "(koi open order nahi)"
    lines = []
    for o in orders:
        parts = [f"#{o['id']}", str(o.get("item") or "")]
        if o.get("spec"):
            parts.append(f"spec {o['spec']}")
        if o.get("quantity") is not None:
            parts.append(f"qty {_num(o['quantity'])} {o.get('unit') or ''}".strip())
        if o.get("rate") is not None:
            parts.append(f"rate {_num(o['rate'])}")
        if o.get("delivery_date"):
            parts.append(f"delivery {o['delivery_date']}")
        lines.append("- " + ", ".join(parts))
    return "\n".join(lines)


def _num(value) -> str:
    f = float(value)
    return str(int(f)) if f.is_integer() else str(f)
