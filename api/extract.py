from http.server import BaseHTTPRequestHandler
import json, re, fitz

class handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_POST(self):
        try:
            n = int(self.headers.get('Content-Length', 0))
            pdf_bytes = self.rfile.read(n)
            vocab = extract_vocab(pdf_bytes)
            body = json.dumps(vocab, ensure_ascii=False).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self._cors()
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            body = json.dumps({'error': str(e)}).encode('utf-8')
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self._cors()
            self.end_headers()
            self.wfile.write(body)

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')


def extract_vocab(pdf_bytes):
    doc   = fitz.open(stream=pdf_bytes, filetype="pdf")
    RX    = doc[0].rect.width * 0.54
    NOISE = re.compile(r'^(Pag\.\s*\d+|ITALIANDO.*|NDO|ITALIA|STORIE.*|#\d+|\*Pdf.*)$', re.I)
    YEAR  = re.compile(r'^\(?\d{4}')

    spans = []
    for pg in range(len(doc)):
        page = doc[pg]
        for b in sorted(page.get_text("dict")["blocks"], key=lambda b: b["bbox"][1]):
            if b["bbox"][0] < RX:
                continue
            if b["type"] == 1:          # image block → skip definition
                spans.append({"kind": "image"})
                continue
            for line in b["lines"]:
                for sp in line["spans"]:
                    t = sp["text"].strip()
                    if not t:
                        continue
                    bold = bool(sp["flags"] & 2**4)
                    spans.append({"kind": "bold" if bold else "text", "text": t})

    entries, ct, cd, ci = [], [], [], False

    def flush():
        term = " ".join(ct).strip(" -():")
        defn = re.sub(r'\(\s+', '(', " ".join(cd).strip())
        if term and not YEAR.match(term):
            entries.append({"term": term, "def": defn})

    for sp in spans:
        if sp["kind"] == "image":
            ci = True
            continue
        t = sp["text"].strip()
        if NOISE.match(t):
            continue
        if sp["kind"] == "bold":
            if t in ("(", "-", "–", "*"):
                if ct: cd.append(t)
                continue
            cont = ct and not cd and not ci and not YEAR.match(t) and not t.endswith(":")
            if cont:
                ct.append(t)
            else:
                if ct: flush()
                ct, cd, ci = [t], [], False
        else:
            if ct: cd.append(t)

    if ct:
        flush()

    return [{"it": e["term"], "def": e["def"]}
            for e in entries if len(e["def"].split()) >= 3]

