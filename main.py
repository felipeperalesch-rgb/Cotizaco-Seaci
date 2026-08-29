from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from supabase import create_client, Client
from datetime import date
from datetime import datetime
from weasyprint import HTML as WeasyHTML
import os
import json
import base64
import hashlib
import html
import hmac
import time
from urllib.parse import quote

# Acceso al cotizador. Configura estos valores como variables secretas en Render.
ADMIN_USER = os.getenv("ADMIN_USER", "").strip()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
SESSION_COOKIE = "seaci_session"
SESSION_MAX_AGE = 12 * 60 * 60


def _session_key() -> bytes:
    # Cambiar la contraseña invalida automáticamente todas las sesiones abiertas.
    return hashlib.sha256(
        f"seaci-session:{ADMIN_USER}:{ADMIN_PASSWORD}".encode("utf-8")
    ).digest()


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def create_session_token() -> str:
    expires_at = int(time.time()) + SESSION_MAX_AGE
    payload = f"{ADMIN_USER}|{expires_at}".encode("utf-8")
    signature = hmac.new(_session_key(), payload, hashlib.sha256).digest()
    return f"{_b64encode(payload)}.{_b64encode(signature)}"


def session_is_valid(token: str | None) -> bool:
    if not token or not ADMIN_USER or not ADMIN_PASSWORD:
        return False

    try:
        payload_part, signature_part = token.split(".", 1)
        payload = _b64decode(payload_part)
        signature = _b64decode(signature_part)
        expected_signature = hmac.new(
            _session_key(), payload, hashlib.sha256
        ).digest()

        if not hmac.compare_digest(signature, expected_signature):
            return False

        username, expires_text = payload.decode("utf-8").rsplit("|", 1)
        return (
            hmac.compare_digest(
                username.encode("utf-8"), ADMIN_USER.encode("utf-8")
            )
            and int(expires_text) >= int(time.time())
        )
    except (ValueError, UnicodeDecodeError):
        return False


def login_is_valid(username: str, password: str) -> bool:
    return (
        bool(ADMIN_USER and ADMIN_PASSWORD)
        and hmac.compare_digest(
            username.encode("utf-8"), ADMIN_USER.encode("utf-8")
        )
        and hmac.compare_digest(
            password.encode("utf-8"), ADMIN_PASSWORD.encode("utf-8")
        )
    )


def safe_next_path(value: str | None) -> str:
    if value and value.startswith("/") and not value.startswith("//"):
        return value
    return "/"


def login_page(next_path: str = "/", error: str = "") -> str:
    safe_next = html.escape(safe_next_path(next_path), quote=True)
    error_html = (
        f'<div class="error">{html.escape(error)}</div>' if error else ""
    )
    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Acceso | Cotizador SEACI</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0; min-height: 100vh; display: grid; place-items: center;
      font-family: Arial, sans-serif; color: #20252b;
      background: linear-gradient(145deg, #12171c, #263039);
    }}
    .card {{
      width: min(92vw, 410px); background: #fff; border-radius: 16px;
      padding: 34px; box-shadow: 0 22px 60px rgba(0,0,0,.38);
    }}
    .brand {{ color: #84bd00; font-size: 26px; font-weight: 800; }}
    h1 {{ margin: 8px 0 6px; font-size: 23px; }}
    p {{ margin: 0 0 24px; color: #66717c; }}
    label {{ display: block; margin: 14px 0 6px; font-weight: 700; }}
    input {{
      width: 100%; padding: 12px 13px; border: 1px solid #cbd2d8;
      border-radius: 9px; font-size: 16px;
    }}
    input:focus {{ outline: 3px solid rgba(132,189,0,.22); border-color: #84bd00; }}
    button {{
      width: 100%; margin-top: 22px; padding: 12px; border: 0;
      border-radius: 9px; background: #84bd00; color: #111;
      font-weight: 800; font-size: 16px; cursor: pointer;
    }}
    button:hover {{ background: #96d600; }}
    .error {{
      margin: 0 0 14px; padding: 10px 12px; border-radius: 8px;
      background: #fde8e8; color: #a21c1c;
    }}
    .foot {{ margin-top: 20px; text-align: center; font-size: 12px; color: #87919a; }}
  </style>
</head>
<body>
  <main class="card">
    <div class="brand">⚡ SEACI</div>
    <h1>Acceso al cotizador</h1>
    <p>Ingresa tus credenciales de administrador.</p>
    {error_html}
    <form method="post" action="/login">
      <input type="hidden" name="next" value="{safe_next}">
      <label for="username">Usuario</label>
      <input id="username" name="username" type="text" autocomplete="username" required autofocus>
      <label for="password">Contraseña</label>
      <input id="password" name="password" type="password" autocomplete="current-password" required>
      <button type="submit">Entrar</button>
    </form>
    <div class="foot">Servicios Eléctricos, Automatización y Control Industrial</div>
  </main>
</body>
</html>"""

# Configura tus credenciales de Supabase (usa variables de entorno o colócalas directamente)
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://groeopgrcwrdwezosihk.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imdyb2VvcGdyY3dyZHdlem9zaWhrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTY3ODM3NDAsImV4cCI6MjA3MjM1OTc0MH0.eY77OAWesw9YtDugKF--O_0QI3a7nXdl7YA_7Ghofhw")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


app = FastAPI(title="Cotizador Supabase")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.middleware("http")
async def protect_cotizador(request: Request, call_next):
    path = request.url.path

    if path != "/health" and (not ADMIN_USER or not ADMIN_PASSWORD):
        return PlainTextResponse(
            "Falta configurar ADMIN_USER y ADMIN_PASSWORD en Render.",
            status_code=503,
        )

    public_paths = {"/health", "/login"}
    if path not in public_paths and not session_is_valid(
        request.cookies.get(SESSION_COOKIE)
    ):
        next_path = quote(safe_next_path(path), safe="/")
        return RedirectResponse(
            url=f"/login?next={next_path}",
            status_code=303,
        )

    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request, next: str = "/"):
    if session_is_valid(request.cookies.get(SESSION_COOKIE)):
        return RedirectResponse(url=safe_next_path(next), status_code=303)
    return HTMLResponse(login_page(next_path=next))


@app.post("/login", response_class=HTMLResponse)
def login_submit(
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/"),
):
    destination = safe_next_path(next)
    if not login_is_valid(username, password):
        return HTMLResponse(
            login_page(
                next_path=destination,
                error="Usuario o contraseña incorrectos.",
            ),
            status_code=401,
        )

    response = RedirectResponse(url=destination, status_code=303)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=create_session_token(),
        max_age=SESSION_MAX_AGE,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )
    return response


@app.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(key=SESSION_COOKIE, path="/")
    return response

from collections import defaultdict

@app.get("/", response_class=HTMLResponse)
def list_quotes(request: Request, search: str = None, status: str = None):
    query = supabase.table("quotes").select("*")

    if status and status != "Todas":
        query = query.eq("status", status)

    response = query.order("date", desc=True).execute()
    quotes = response.data if response and response.data else []

    # Obtener todos los items de todas las cotizaciones en una sola consulta
    items_response = supabase.table("items").select("*").execute()
    all_items = items_response.data if items_response and items_response.data else []

    # Agrupar por quote_id usando defaultdict
    items_por_cotizacion = defaultdict(list)
    for item in all_items:
        items_por_cotizacion[item["quote_id"]].append(item)

    filtered_quotes = []

    for q in quotes:
        q["folio"] = f"SE{800 + q['id']:05d}"

        if isinstance(q.get("date"), str):
            try:
                fecha = datetime.fromisoformat(q["date"])
                q["formatted_date"] = fecha.strftime('%d-%m-%Y')
            except ValueError:
                q["formatted_date"] = "Fecha inválida"
        else:
            q["formatted_date"] = "Sin fecha"

        q["servicios"] = items_por_cotizacion[q["id"]]

        if search:
            search_lower = search.lower()
            cliente_ok = search_lower in q["client_name"].lower()
            servicio_ok = any(search_lower in it["description"].lower() for it in q["servicios"])
            if cliente_ok or servicio_ok:
                filtered_quotes.append(q)
        else:
            filtered_quotes.append(q)

    return templates.TemplateResponse(
    request,
    "index.html",
    {
        "quotes": filtered_quotes,
        "search": search,
        "status": status or "Todas"
    }
)




@app.get("/quotes/new", response_class=HTMLResponse)
def new_quote_form(request: Request):
    return templates.TemplateResponse(
        request,
        "quote_new.html",
        {}
    )

@app.get("/quotes/{quote_id}/edit", response_class=HTMLResponse)
def edit_quote(quote_id: int, request: Request):
    # Obtener la cotización
    quote = supabase.table("quotes").select("*").eq("id", quote_id).single().execute().data
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")

    # Obtener servicios relacionados
    items = supabase.table("items").select("*").eq("quote_id", quote_id).execute().data
    quote["folio"] = f"SE{800 + quote['id']:05d}"
    
    # Serializar los items para JS
    items_json = json.dumps(items)

    return templates.TemplateResponse(
    request,
    "quote_edit.html",
    {
        "quote": quote,
        "items_json": items_json
    }
)
@app.post("/quotes/{quote_id}/update")
async def update_quote(
    quote_id: int,
    request: Request,
    client_name: str = Form(...),
    client_company: str = Form(""),
    client_email: str = Form(""),
    client_phone: str = Form(""),
    client_address: str = Form(""),
    currency: str = Form("MXN"),
    tax_rate: float = Form(0.0),
    discount_rate: float = Form(0.0),
    notes: str = Form(""),
    validity: str = Form("7 días."),
    payment_terms: str = Form(""),
    warranty: str = Form(""),
    status: str = Form(""),
    items_json: str = Form("[]")
):
    # Calcular totales
    items = json.loads(items_json or "[]")
    subtotal = sum([float(it.get("quantity", 0)) * float(it.get("unit_price", 0)) for it in items])
    discount_amount = subtotal * (discount_rate / 100)
    base = subtotal - discount_amount
    tax_amount = base * (tax_rate / 100)
    total = base + tax_amount

    # Actualizar cotización
    supabase.table("quotes").update({
        "client_name": client_name,
        "client_company": client_company,
        "client_email": client_email,
        "client_phone": client_phone,
        "client_address": client_address,
        "currency": currency,
        "tax_rate": tax_rate,
        "discount_rate": discount_rate,
        "notes": notes,
        "validity": validity,
        "payment_terms": payment_terms,
        "warranty": warranty,
        "status": status,
        "subtotal": subtotal,
        "discount_amount": discount_amount,
        "tax_amount": tax_amount,
        "total": total
    }).eq("id", quote_id).execute()

    # Eliminar servicios anteriores
    supabase.table("items").delete().eq("quote_id", quote_id).execute()

    # Insertar servicios nuevos
    for it in items:
        it["quote_id"] = quote_id
        it["amount"] = float(it.get("quantity", 0)) * float(it.get("unit_price", 0))

    supabase.table("items").insert(items).execute()

    return RedirectResponse(url=f"/quotes/{quote_id}", status_code=303)


@app.post("/quotes/create")
async def create_quote(
    request: Request,
    client_name: str = Form(...),
    client_company: str = Form(""),
    client_email: str = Form(""),
    client_phone: str = Form(""),
    client_address: str = Form(""),
    currency: str = Form("MXN"),
    tax_rate: float = Form(0.0),
    discount_rate: float = Form(0.0),
    notes: str = Form(""),
    validity: str = Form("7 días."),
    payment_terms: str = Form(""),
    warranty: str = Form(""),
    items_json: str = Form("[]")
):
    items = json.loads(items_json or "[]")
    subtotal = sum([float(it.get("quantity", 0)) * float(it.get("unit_price", 0)) for it in items])
    discount_amount = subtotal * (discount_rate / 100)
    base = subtotal - discount_amount
    tax_amount = base * (tax_rate / 100)
    total = base + tax_amount

    quote_data = {
        "client_name": client_name,
        "client_company": client_company,
        "client_email": client_email,
        "client_phone": client_phone,
        "client_address": client_address,
        "currency": currency,
        "tax_rate": tax_rate,
        "discount_rate": discount_rate,
        "notes": notes,
        "validity": validity,
        "payment_terms": payment_terms,
        "warranty": warranty,
        "subtotal": subtotal,
        "discount_amount": discount_amount,
        "tax_amount": tax_amount,
        "total": total,
        "date": date.today().isoformat()
    }

    result = supabase.table("quotes").insert(quote_data).execute()
    quote = result.data[0]
    quote_id = quote["id"]

    for it in items:
        it["quote_id"] = quote_id
        it["amount"] = float(it.get("quantity", 0)) * float(it.get("unit_price", 0))

    supabase.table("items").insert(items).execute()

    return RedirectResponse(url=f"/quotes/{quote_id}", status_code=303)

@app.get("/quotes/{quote_id}", response_class=HTMLResponse)
def view_quote(quote_id: int, request: Request):
    quote = supabase.table("quotes").select("*").eq("id", quote_id).single().execute().data
    items = supabase.table("items").select("*").eq("quote_id", quote_id).execute().data
    quote["folio"] = f"SE{800 + quote['id']:05d}"

    # ✅ Formatear la fecha para evitar .strftime en el template
    if isinstance(quote.get("date"), str):
        try:
            fecha = datetime.fromisoformat(quote["date"])
            quote["formatted_date"] = fecha.strftime('%d-%m-%Y')
        except ValueError:
            quote["formatted_date"] = "Fecha inválida"
    else:
        quote["formatted_date"] = "Sin fecha"

    return templates.TemplateResponse(
    request,
    "quote_view.html",
    {
        "quote": quote,
        "items": items,
        "settings": {}
    }
)


@app.get("/quotes/{quote_id}/pdf")
def generate_pdf(quote_id: int):
    quote = supabase.table("quotes").select("*").eq("id", quote_id).single().execute().data
    items = supabase.table("items").select("*").eq("quote_id", quote_id).execute().data
    quote["folio"] = f"SE{800 + quote['id']:05d}"

    if isinstance(quote.get("date"), str):
        try:
            fecha = datetime.fromisoformat(quote["date"])
            quote["formatted_date"] = fecha.strftime('%d-%m-%Y')
        except ValueError:
            quote["formatted_date"] = "Fecha inválida"
    else:
        quote["formatted_date"] = "Sin fecha"

    static_dir = os.path.join(os.path.dirname(__file__), "static")
    logo_path = os.path.join(static_dir, "logo.png")

    html_content = templates.get_template("quote_pdf.html").render(
        quote=quote,
        items=items,
        settings={},
        logo_path=f"file://{logo_path}"  # O cámbialo si falla
    )

    output_path = f"/tmp/cotizacion_{quote['folio']}.pdf"  # Mejor usar /tmp en Render
    WeasyHTML(string=html_content).write_pdf(output_path)

    return FileResponse(output_path, media_type="application/pdf", filename=f"Cotización_{quote['folio']}.pdf")


@app.post("/quotes/{quote_id}/status")
def update_status(quote_id: int, status: str = Form(...)):
    supabase.table("quotes").update({"status": status}).eq("id", quote_id).execute()
    return RedirectResponse(url="/", status_code=303)

@app.post("/quotes/{quote_id}/delete")
def delete_quote(quote_id: int):
    supabase.table("items").delete().eq("quote_id", quote_id).execute()
    supabase.table("quotes").delete().eq("id", quote_id).execute()
    return RedirectResponse(url="/", status_code=303)

    

@app.get("/api/clientes")
def get_clients_autocomplete():
    data = supabase.table("quotes").select("client_name,client_company,client_email,client_phone,client_address").execute().data
    seen = set()
    result = []
    for c in data:
        key = tuple(c.values())
        if key not in seen:
            seen.add(key)
            result.append({
                "name": c["client_name"],
                "company": c["client_company"],
                "email": c["client_email"],
                "phone": c["client_phone"],
                "address": c["client_address"]
            })
    return result
