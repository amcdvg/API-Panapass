import os
import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from capmonstercloudclient import CapMonsterClient, ClientOptions
from capmonstercloudclient.requests import RecaptchaV3ProxylessRequest
import time
# --- CONFIGURACIÓN ---
# Se recomienda usar variables de entorno en Koyeb por seguridad
API_KEY = os.getenv("CAPMONSTER_API_KEY", "66707c7fb22e8a95741524b7efbbf02a")

client_options = ClientOptions(api_key=API_KEY)
cap_monster_client = CapMonsterClient(options=client_options)

app = FastAPI(title="API ENA Panamá - Consulta por URL")

# --- CONFIGURACIÓN DE CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["GET"], # Ahora solo necesitamos GET
    allow_headers=["*"],
)

# --- FUNCIONES DE APOYO ---
async def solve_recaptcha(url: str, site_key: str):
    try:
        request = RecaptchaV3ProxylessRequest(
            websiteUrl=url,
            websiteKey=site_key,
            isInvisible=True
        )
        result = await cap_monster_client.solve_captcha(request)
        token = result.get('gRecaptchaResponse')
        if not token:
            raise ValueError("No se recibió token de CapMonster")
        return token
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al resolver CAPTCHA: {str(e)}")

# --- ENDPOINTS ---

@app.get("/")
async def root():
    return {"status": "online", "message": "API de ENA lista para consultas por URL"}

# Ejemplo de uso: https://tu-app.koyeb.app/consultar/placa/ED6266
@app.get("/consultar/placa/{placa}")
async def api_get_placa(placa: str):
    # 1. Resolver Captcha
    token = await solve_recaptcha(
        url="https://ena.com.pa/consulta-de-placa/",
        site_key="6LfdGNwqAAAAADWxDE1qnjJ4ySjBuoZdqvBzCv1h"
    )

    # 2. Petición a ENA
    target_url = 'https://ena.com.pa/apiv2/index.php/get-morosidad-tag/json'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
    }
    payload = {'plate': placa, 'captcha_token': token}

    async with httpx.AsyncClient(timeout=45.0) as client:
        try:
            response = await client.post(target_url, headers=headers, data=payload)
            resultado = response.json()
            if isinstance(resultado, dict):
                if resultado.get("success") == False:
                    print(f"Error API placa: {resultado.get('message')}")
                    if "reCAPTCHA" in str(resultado.get('message')):
                        print("Reintentando con nuevo token...")
                        time.sleep(2)
                        return api_get_placa(placa)
                    return 0.0
                    
                if "saldo" in resultado:
                    saldo = float(resultado["saldo"])
                elif "balanceAmount" in resultado:
                    saldo = float(resultado["balanceAmount"])
                elif "totalAmount" in resultado:
                    saldo = float(resultado["totalAmount"])
                elif "monto" in resultado:
                    saldo = float(resultado["monto"])
                else:
                    return 0.0
                
                # Verificar si es negativo (moroso)
                if resultado.get("chkDefaulter") == '1' or resultado.get("defaulter") == '1' or resultado.get("esMoroso") == True:
                    saldo = -abs(saldo)
                else:
                    saldo = abs(saldo)
                    
                
                return {'plate': placa, 'saldo': saldo/100}
            
        except Exception as e:
            return {'placa': placa, 'saldo': "NoEnc"}

# Ejemplo de uso: https://tu-app.koyeb.app/consultar/panapass/287097
@app.get("/consultar/panapass/{panapass}")
async def api_get_panapass(panapass: str):
    # 1. Resolver Captcha
    token = await solve_recaptcha(
        url="https://ena.com.pa/consulta-tu-saldo/",
        site_key="6LcgI9wqAAAAAEPWc0dOvIwJakaL7crE9LH9951j"
    )

    # 2. Petición a ENA
    target_url = 'https://ena.com.pa/apiv2/index.php/get-saldo-panapass/json'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
    }
    payload = {'panapass': panapass, 'captcha_token': token}

    async with httpx.AsyncClient(timeout=45.0) as client:
        try:
            response = await client.post(target_url, headers=headers, data=payload)
            resultado = response.json()
        
            if isinstance(resultado, dict):
                if resultado.get("success") == False:
                    #print(f"Error API: {resultado.get('message')}")
                    if "reCAPTCHA" in str(resultado.get('message')):
                        #print("Reintentando con nuevo token...")
                        time.sleep(2)
                        return api_get_panapass(panapass)
                    
                    return {'Panapass': panapass, 'saldo': 0.0}
                if resultado.get("success") == False and resultado.get("message") == "Cliente/Cuenta no encontrado":
                        return {'Panapass': panapass, 'saldo': "NoEnc"}    
                if "saldo" in resultado:
                    saldo = float(resultado["saldo"])
                    #print(f"Saldo obtenido: {saldo}")
                    return {'Panapass': panapass, 'saldo': saldo}
                elif "balance" in resultado:
                    saldo = float(resultado["balance"])
                    #print(f"Saldo obtenido: {saldo}")
                    return {'Panapass': panapass, 'saldo': saldo}
                elif "data" in resultado and isinstance(resultado["data"], dict):
                    if "saldo" in resultado["data"]:
                        saldo = float(resultado["data"]["saldo"])
                        #print(f"Saldo obtenido: {saldo}")
                        return {'Panapass': panapass, 'saldo': saldo}
            
            return {'Panapass': panapass, 'saldo': 0.0}
        except Exception as e:
            return {'Panapass': panapass, 'saldo': "NoEnc"}

# --- INICIO DEL SERVIDOR ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)