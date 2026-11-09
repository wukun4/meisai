"""Download NASA POWER paired July climatological states; preserve raw metadata.

No design-weather values are inferred from these monthly averages.
Run once online; make_figures.py uses the archived data offline.
"""
from pathlib import Path
import concurrent.futures, datetime, hashlib, json, time, urllib.request

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
DATA.mkdir(exist_ok=True)
# Representative geographic samples, not weather-station observations.
POINTS = [
 ('Seattle',47.61,-122.33),('Spokane',47.66,-117.43),('Portland',45.52,-122.68),
 ('Boise',43.62,-116.20),('Eureka',40.80,-124.16),('Reno',39.53,-119.81),
 ('Sacramento',38.58,-121.49),('San Francisco',37.77,-122.42),('Los Angeles',34.05,-118.24),
 ('San Diego',32.72,-117.16),('Las Vegas',36.17,-115.14),('Phoenix',33.45,-112.07),
 ('Tucson',32.22,-110.97),('Flagstaff',35.20,-111.65),('Salt Lake City',40.76,-111.89),
 ('Elko',40.83,-115.76),('Helena',46.59,-112.04),('Billings',45.78,-108.50),
 ('Missoula',46.87,-114.00),('Kalispell',48.20,-114.31),('Denver',39.74,-104.99),
 ('Grand Junction',39.06,-108.55),('Albuquerque',35.08,-106.65),('El Paso',31.76,-106.49),
 ('Cheyenne',41.14,-104.82),('Casper',42.85,-106.33),('Bismarck',46.81,-100.78),
 ('Fargo',46.88,-96.79),('Rapid City',44.08,-103.23),('Sioux Falls',43.55,-96.73),
 ('Omaha',41.26,-95.94),('North Platte',41.14,-100.76),('Wichita',37.69,-97.34),
 ('Kansas City',39.10,-94.58),('Oklahoma City',35.47,-97.52),('Amarillo',35.22,-101.83),
 ('Dallas',32.78,-96.80),('Austin',30.27,-97.74),('Houston',29.76,-95.37),
 ('Brownsville',25.90,-97.50),('Minneapolis',44.98,-93.27),('Duluth',46.79,-92.10),
 ('Chicago',41.88,-87.63),('St Louis',38.63,-90.20),('Little Rock',34.75,-92.29),
 ('New Orleans',29.95,-90.07),('Memphis',35.15,-90.05),('Jackson',32.30,-90.18),
 ('Nashville',36.16,-86.78),('Indianapolis',39.77,-86.16),('Detroit',42.33,-83.05),
 ('Green Bay',44.51,-88.02),('Marquette',46.54,-87.40),('Columbus',39.96,-83.00),
 ('Atlanta',33.75,-84.39),('Birmingham',33.52,-86.80),('Tallahassee',30.44,-84.28),
 ('Miami',25.76,-80.19),('Tampa',27.95,-82.46),('Jacksonville',30.33,-81.66),
 ('Charleston',32.78,-79.93),('Charlotte',35.23,-80.84),('Raleigh',35.78,-78.64),
 ('Richmond',37.54,-77.44),('Washington DC',38.91,-77.04),('Pittsburgh',40.44,-79.99),
 ('Buffalo',42.89,-78.87),('New York City',40.71,-74.01),('Boston',42.36,-71.06),
 ('Burlington',44.48,-73.21),('Portland Maine',43.66,-70.26),('Caribou',46.86,-68.01),
 ('Honolulu',21.31,-157.86),('Lihue',21.97,-159.37),('Kahului',20.89,-156.47),
 ('Hilo',19.73,-155.09),('Kona',19.64,-155.99)]

def fetch(point):
    name, lat, lon = point
    slug = name.lower().replace(' ', '_')
    target = DATA / ('power_' + slug + '.json')
    url = ('https://power.larc.nasa.gov/api/temporal/climatology/point?'
           f'parameters=T2M,RH2M,PS&community=SB&longitude={lon}&latitude={lat}&format=JSON')
    for attempt in range(4):
        try:
            if target.exists():
                payload = json.loads(target.read_text())
            else:
                req = urllib.request.Request(url, headers={'User-Agent':'CP-SET-reproducible-figure/1.0'})
                with urllib.request.urlopen(req, timeout=50) as response:
                    raw = response.read()
                payload = json.loads(raw)
                target.write_bytes(raw)
            pars = payload['properties']['parameter']
            values = {p: pars[p]['JUL'] for p in ('T2M','RH2M','PS')}
            assert all(v != -999 for v in values.values())
            return dict(name=name, latitude=lat, longitude=lon, **values,
                        period=payload['header']['range'], source_url=url,
                        raw_file=target.name,
                        sha256=hashlib.sha256(target.read_bytes()).hexdigest())
        except Exception:
            if attempt == 3: raise
            time.sleep(2 * (attempt+1))

if __name__ == '__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        points = list(pool.map(fetch, POINTS))
    assert len({p['period'] for p in points}) == 1
    out = dict(retrieved_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
               description='NASA POWER July monthly mean states; geographic samples, not stations; wet bulb evaluated at paired mean T/RH/pressure.',
               points=points)
    (DATA/'climate_samples.json').write_text(json.dumps(out, indent=2))
    print(f'Archived {len(points)} samples; period: {points[0]["period"]}')
