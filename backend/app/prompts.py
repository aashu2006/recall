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
