import csv
from datetime import datetime
import json
import os
import urllib.request
import zipfile

# URL pública del GTFS oficial de Renfe Cercanías
RENFE_GTFS_URL = (
    "https://gtfs.renfe.com/GTFS_CERCANIAS.zip"  # Ajustar a la URL oficial
)
OUTPUT_JSON = "cercanias_valencia_schedule.json"

VINAROS_STATION_KEYWORDS = [
    "benicàssim",
    "benicasim",
    "orpesa",
    "oropesa",
    "torreblanca",
    "alcalà de xivert",
    "alcala de xivert",
    "benicarló",
    "benicarlo",
    "vinaròs",
    "vinaros",
]


def download_and_extract_gtfs():
  """Descarga y descomprime los archivos de Renfe automáticamente."""
  print("- Descargando último paquete GTFS de Renfe...")
  zip_path = "gtfs_latest.zip"
  try:
    urllib.request.urlretrieve(RENFE_GTFS_URL, zip_path)
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
      zip_ref.extractall(".")
    print("  [OK] GTFS descargado y descomprimido correctamente.")
  except Exception as e:
    print(f"⚠️ No se pudo descargar el GTFS en vivo: {e}. Usando archivos locales si existen.")


def clean_dict_reader(f):
  reader = csv.DictReader(f)
  if reader.fieldnames:
    reader.fieldnames = [f.strip() for f in reader.fieldnames]
  for row in reader:
    if row:
      yield {k.strip(): (v.strip() if v else "") for k, v in row.items() if k}


def format_station_name(name):
  if not name:
    return ""
  EXACT_FIXES = {
      "valencia nord": "València Nord",
      "valencia-nord": "València Nord",
      "valencia sant isidre": "València Sant Isidre",
      "valencia cabanyal": "València-Cabanyal",
      "valencia-cabanyal": "València-Cabanyal",
      "castello de la plana": "Castelló de la Plana",
      "castellon de la plana": "Castelló de la Plana",
      "castello": "Castelló",
      "castellon": "Castelló",
      "xativa": "Xàtiva",
      "vinaros": "Vinaròs",
      "benicassim": "Benicàssim",
      "alcala de xivert": "Alcalà de Xivert",
      "alcalà de xivert": "Alcalà de Xivert",
      "benicarlo-peniscola": "Benicarló-Peñíscola",
      "benicarlo-peñiscola": "Benicarló-Peñíscola",
      "orpesa": "Orpesa / Oropesa del Mar",
      "oropesa del mar": "Orpesa / Oropesa del Mar",
      "xirivella-l'alter": "Xirivella-L'Alter",
      "xirivella-l alter": "Xirivella-L'Alter",
      "xirivella l'alter": "Xirivella-L'Alter",
      "alfafar-benetusser": "Alfafar-Benetússer",
      "alfafar-benetússer": "Alfafar-Benetússer",
  }
  clean_lower = name.strip().lower()
  if clean_lower in EXACT_FIXES:
    return EXACT_FIXES[clean_lower]

  LOWER_WORDS = {
      "de",
      "del",
      "d'",
      "l'",
      "la",
      "les",
      "el",
      "els",
      "los",
      "las",
      "a",
      "en",
      "i",
      "y",
  }
  words = name.strip().split()
  formatted_words = []
  for idx, word in enumerate(words):
    subparts = word.split("-")
    formatted_subparts = []
    for s_idx, sub in enumerate(subparts):
      sub_lower = sub.lower()
      if "'" in sub_lower:
        apo_parts = sub_lower.split("'")
        formatted_apo = [
            apo.capitalize() if a_idx > 0 else apo.lower()
            for a_idx, apo in enumerate(apo_parts)
        ]
        formatted_subparts.append("'".join(formatted_apo))
      elif sub_lower in LOWER_WORDS and idx > 0 and s_idx == 0:
        formatted_subparts.append(sub_lower)
      else:
        formatted_subparts.append(sub.capitalize())
    formatted_words.append("-".join(formatted_subparts))
  return " ".join(formatted_words)


def fix_gtfs_time_full(time_str):
  if not time_str:
    return ""
  parts = time_str.strip().split(":")
  if len(parts) == 3:
    try:
      hours = int(parts[0]) % 24
      return f"{hours:02d}:{parts[1]}:{parts[2]}"
    except ValueError:
      pass
  return time_str[:8]


def clean_coord(val):
  if not val:
    return 0.0
  val_str = str(val).strip().replace(",", ".")
  parts = val_str.split(".")
  if len(parts) > 2:
    val_str = parts[0] + "." + "".join(parts[1:])
  try:
    f = float(val_str)
    while f > 180 or f < -180:
      f /= 10.0
    return round(f, 6)
  except ValueError:
    return 0.0


def process_gtfs():
  # Obtener fecha dinámica de HOY en formato YYYYMMDD (ej. 20260723)
  today_str = datetime.now().strftime("%Y%m%d")
  print(f"- Fecha dinámica actual para filtrado: {today_str}")

  download_and_extract_gtfs()

  active_services = set()
  if os.path.exists("calendar.txt"):
    with open("calendar.txt", mode="r", encoding="utf-8-sig") as f:
      for row in clean_dict_reader(f):
        s_id = row.get("service_id", "")
        e_date = row.get("end_date", "") or row.get("start_date", "")
        if e_date and e_date >= today_str:
          active_services.add(s_id)

  stops_dict = {}
  wheelchair_map = {}
  stops_txt_names = {}

  if os.path.exists("stops.txt"):
    with open("stops.txt", mode="r", encoding="utf-8-sig") as f:
      for row in clean_dict_reader(f):
        s_id = row.get("stop_id", "")
        raw_name = row.get("stop_name", "")
        if s_id:
          wheelchair_map[s_id] = row.get("wheelchair_boarding", "0") == "1"
          stops_txt_names[s_id] = format_station_name(raw_name)

  if os.path.exists("estaciones_cercanias_valencia.csv"):
    with open(
        "estaciones_cercanias_valencia.csv", mode="r", encoding="latin-1"
    ) as f:
      reader = csv.reader(f, delimiter=";")
      for r in reader:
        if r and (r[0].isdigit() or r[0].startswith("6")):
          s_id = r[0].strip()
          stops_dict[s_id] = {
              "stop_id": s_id,
              "nombre": (
                  format_station_name(r[1].strip())
                  if len(r) > 1
                  else f"Estación {s_id}"
              ),
              "lat": clean_coord(r[2]) if len(r) > 2 else 0.0,
              "lon": clean_coord(r[3]) if len(r) > 3 else 0.0,
              "wheelchair_accessible": wheelchair_map.get(s_id, False),
          }

  if os.path.exists("stops.txt"):
    with open("stops.txt", mode="r", encoding="utf-8-sig") as f:
      for row in clean_dict_reader(f):
        s_id = row.get("stop_id", "")
        raw_name = row.get("stop_name", "")
        if any(kw in raw_name.lower() for kw in VINAROS_STATION_KEYWORDS):
          if s_id not in stops_dict:
            stops_dict[s_id] = {
                "stop_id": s_id,
                "nombre": format_station_name(raw_name),
                "lat": clean_coord(row.get("stop_lat", 0)),
                "lon": clean_coord(row.get("stop_lon", 0)),
                "wheelchair_accessible": wheelchair_map.get(s_id, False),
            }

  route_map = {}
  if os.path.exists("routes.txt"):
    with open("routes.txt", mode="r", encoding="utf-8-sig") as f:
      for row in clean_dict_reader(f):
        r_id = row.get("route_id", "")
        r_short = row.get("route_short_name", "").upper()
        if r_short in {"ER02", "ER-02", "C6", "C-6"}:
          route_map[r_id] = "C6"
        elif r_short in {
            "C1",
            "C2",
            "C3",
            "C4",
            "C5",
            "C-1",
            "C-2",
            "C-3",
            "C-4",
            "C-5",
        }:
          route_map[r_id] = r_short.replace("-", "")

  trips_info = {}
  if os.path.exists("trips.txt"):
    with open("trips.txt", mode="r", encoding="utf-8-sig") as f:
      for row in clean_dict_reader(f):
        t_id = row.get("trip_id", "")
        r_id = row.get("route_id", "")
        s_id = row.get("service_id", "")
        if r_id in route_map and (not active_services or s_id in active_services):
          trips_info[t_id] = {
              "linea": route_map[r_id],
              "destino": format_station_name(
                  row.get("trip_headsign", "").strip()
              ),
              "last_stop_id": None,
              "max_seq": -1,
          }

  station_arrivals = []
  if os.path.exists("stop_times.txt"):
    with open("stop_times.txt", mode="r", encoding="utf-8-sig") as f:
      for row in clean_dict_reader(f):
        s_id = row.get("stop_id", "")
        t_id = row.get("trip_id", "")
        if t_id in trips_info:
          seq = int(row.get("stop_sequence", 0) or 0)
          if seq > trips_info[t_id]["max_seq"]:
            trips_info[t_id]["max_seq"] = seq
            trips_info[t_id]["last_stop_id"] = s_id
          if s_id in stops_dict:
            arr_time = fix_gtfs_time_full(
                row.get("arrival_time") or row.get("departure_time", "")
            )
            if arr_time:
              station_arrivals.append((s_id, t_id, arr_time))

  for t_id, meta in trips_info.items():
    if not meta["destino"] and meta["last_stop_id"]:
      last_id = meta["last_stop_id"]
      meta["destino"] = stops_dict.get(
          last_id, {}
      ).get("nombre") or stops_txt_names.get(last_id, "")

  station_horarios = {}
  for s_id, t_id, arr_time in station_arrivals:
    if s_id not in station_horarios:
      station_horarios[s_id] = {}
    meta = trips_info[t_id]
    key = (meta["linea"], meta["destino"] or "Destino no especificado", arr_time)
    if key not in station_horarios[s_id]:
      station_horarios[s_id][key] = []
    station_horarios[s_id][key].append(t_id)

  final_output = []
  for s_id, s_data in stops_dict.items():
    if s_id in station_horarios:
      horarios_list = []
      lines_at_stop = set()
      for (linea, destino, llegada), trip_ids in station_horarios[s_id].items():
        lines_at_stop.add(linea)
        horarios_list.append({
            "linea": linea,
            "destino": destino,
            "llegada": llegada,
            "trip_ids": trip_ids,
        })
      horarios_list.sort(key=lambda x: x["llegada"])
      final_output.append({
          "stop_id": s_data["stop_id"],
          "nombre": s_data["nombre"],
          "lat": s_data["lat"],
          "lon": s_data["lon"],
          "wheelchair_accessible": s_data["wheelchair_accessible"],
          "lineas": sorted(list(lines_at_stop)),
          "horarios": horarios_list,
      })

  with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(final_output, f, ensure_ascii=False, indent=2)

  print(
      f"¡Generación dinámica completada! Estaciones: {len(final_output)}"
  )


if __name__ == "__main__":
  process_gtfs()