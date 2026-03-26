import math
import httpx
import re
from typing import List, Tuple, Dict, Any
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
import time

# Simple in-memory cache for geocoding to avoid hitting Nominatim limits and speed up requests
_GEOCODE_CACHE: Dict[str, Tuple[float, float]] = {}
geolocator = Nominatim(user_agent="gestao_estoque_saas_router_v2")

async def get_address_from_viacep(address_text: str) -> str:
    """
    Tenta extrair o CEP da string e busca dados oficiais na API do ViaCEP.
    Retorna a string limpa para o Nominatim ou a string original como fallback.
    """
    if not address_text:
        return address_text

    # Extrai o CEP (formato 00000-000 ou 00000000)
    cep_match = re.search(r'\b\d{5}-?\d{3}\b', address_text)
    if not cep_match:
        return address_text

    cep = cep_match.group(0).replace('-', '')
    
    # Extrai o Número (pega a primeira sequência de dígitos que não seja o CEP, geralmente após a vírgula)
    # Ex: "Rua Ficticia, 123, Bairro..."
    parts = address_text.split(',')
    numero = ""
    if len(parts) > 1:
        num_match = re.search(r'\d+', parts[1])
        if num_match:
            numero = num_match.group(0)

    try:
        url = f"https://viacep.com.br/ws/{cep}/json/"
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            
            if not data.get("erro"):
                logradouro = data.get("logradouro", "")
                localidade = data.get("localidade", "")
                uf = data.get("uf", "")
                
                if logradouro and localidade and uf:
                    # Monta a string perfeita
                    numero_str = f", {numero}" if numero else ""
                    clean_address = f"{logradouro}{numero_str}, {localidade}, {uf}, {cep}, Brazil"
                    print(f"[ViaCEP] Sanitizado: '{address_text}' -> '{clean_address}'")
                    return clean_address
    except Exception as e:
        print(f"[ViaCEP] Falha ao consultar CEP {cep}: {e}")
        
    return address_text

async def get_coordinates_for_address(address: str) -> Tuple[float, float]:
    """
    Converts an address string to (latitude, longitude) using Nominatim.
    Uses in-memory cache to save bandwidth.
    Returns (0.0, 0.0) if not found.
    """
    # Enriquecimento via ViaCEP antes do Geocode
    clean_address = await get_address_from_viacep(address)

    if clean_address in _GEOCODE_CACHE:
        return _GEOCODE_CACHE[clean_address]
        
    try:
        # Rate limit do Nominatim (1 req/sec)
        time.sleep(1)
        location = geolocator.geocode(clean_address, timeout=10)
        if location:
            coords = (location.latitude, location.longitude)
            _GEOCODE_CACHE[clean_address] = coords
            print(f"[Geocode] Sucesso: '{clean_address}' -> {coords}")
            return coords
        else:
            print(f"[Geocode] Falha: Endereço não encontrado: '{clean_address}'")
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        print(f"[Routing] Geocode error for '{clean_address}': {e}")
        
    return (0.0, 0.0)

def calculate_euclidean_distance_matrix(coords: List[Tuple[float, float]]) -> List[List[float]]:
    """
    Fallback method: Calculates Euclidean distance (straight line) if OSRM fails.
    Returns a matrix of distances (mocked as duration for the solver to work).
    """
    matrix = []
    for i in range(len(coords)):
        row = []
        for j in range(len(coords)):
            if i == j:
                row.append(0.0)
            else:
                lat1, lon1 = coords[i]
                lat2, lon2 = coords[j]
                # Very rough euclidean distance just for fallback
                dist = math.sqrt((lat2 - lat1)**2 + (lon2 - lon1)**2) * 111.0 # approx km
                row.append(dist)
        matrix.append(row)
    return matrix

async def get_osrm_route(coordinates: List[Tuple[float, float]]) -> Dict[str, Any]:
    """
    Calls public OSRM API to get the route geometry and steps between points.
    coordinates format: [(lat, lon), (lat, lon), ...]
    """
    if not coordinates or len(coordinates) < 2:
        return {}

    # OSRM expects coordinates as {longitude},{latitude}
    coords_str = ";".join([f"{lon},{lat}" for lat, lon in coordinates])
    url = f"http://router.project-osrm.org/route/v1/driving/{coords_str}?steps=true&geometries=geojson&overview=full"
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            
            if data.get("code") == "Ok":
                routes = data.get("routes", [])
                if routes:
                    return routes[0]
            else:
                print(f"[Routing] OSRM Route API returned non-Ok code: {data.get('code')}")
    except Exception as e:
        print(f"[Routing] OSRM Route API call failed: {e}")
        
    return {}
async def get_osrm_distance_matrix(coordinates: List[Tuple[float, float]]) -> Tuple[List[List[float]], List[List[float]]]:
    """
    Calls public OSRM API to get real driving distances and durations.
    coordinates format: [(lat, lon), (lat, lon), ...]
    Returns: (distance_matrix_meters, duration_matrix_seconds)
    """
    if not coordinates or len(coordinates) < 2:
        return [], []

    # OSRM expects coordinates as {longitude},{latitude}
    coords_str = ";".join([f"{lon},{lat}" for lat, lon in coordinates])
    url = f"http://router.project-osrm.org/table/v1/driving/{coords_str}?annotations=distance,duration"
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            
            if data.get("code") == "Ok":
                return data.get("distances", []), data.get("durations", [])
            else:
                print(f"[Routing] OSRM Matrix API returned non-Ok code: {data.get('code')}")
    except Exception as e:
        print(f"[Routing] OSRM API call failed: {e}")
        
    # Fallback to Euclidean
    print("[Routing] Using Euclidean fallback")
    fallback_matrix = calculate_euclidean_distance_matrix(coordinates)
    return fallback_matrix, fallback_matrix # Return same matrix for both as fallback

def solve_vrp_ortools(duration_matrix: List[List[float]], num_vehicles: int = 1, depot: int = 0) -> Dict[str, Any]:
    """
    Uses OR-Tools to solve the Vehicle Routing Problem based on the duration matrix.
    Minimizes total travel time.
    """
    # Create the routing index manager.
    manager = pywrapcp.RoutingIndexManager(len(duration_matrix), num_vehicles, depot)

    # Create Routing Model.
    routing = pywrapcp.RoutingModel(manager)

    # Create and register a transit callback.
    def time_callback(from_index, to_index):
        # Convert from routing variable Index to duration matrix NodeIndex.
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        # Multiply by 100 to convert float to int (OR-Tools requires integers for weights)
        return int(duration_matrix[from_node][to_node] * 100)

    transit_callback_index = routing.RegisterTransitCallback(time_callback)

    # Define cost of each arc.
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # Setting first solution heuristic.
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)

    # Solve the problem.
    solution = routing.SolveWithParameters(search_parameters)

    if not solution:
        return {"error": "Nenhuma solução encontrada pelo OR-Tools."}

    # Extract solution
    index = routing.Start(0)
    route_sequence = []
    route_time = 0
    
    while not routing.IsEnd(index):
        node_index = manager.IndexToNode(index)
        route_sequence.append(node_index)
        previous_index = index
        index = solution.Value(routing.NextVar(index))
        route_time += routing.GetArcCostForVehicle(previous_index, index, 0)
        
    # Add depot at the end
    route_sequence.append(manager.IndexToNode(index))

    return {
        "sequence": route_sequence,
        "total_time_seconds": route_time / 100.0 # Convert back from int scaling
    }

async def calculate_route(addresses: List[str]) -> Dict[str, Any]:
    """
    Main orchestration function.
    1. Geocodes addresses
    2. Gets OSRM matrices
    3. Solves with OR-Tools
    4. Calculates total real metrics
    """
    if not addresses:
        return {"error": "Lista de endereços vazia."}
        
    if len(addresses) == 1:
         return {
            "sequence": [0],
            "total_distance_km": 0.0,
            "total_eta_minutes": 0.0
        }

    # 1. Geocode
    coordinates = []
    for addr in addresses:
        # Pega a lat/lon do OpenStreetMap
        coords = await get_coordinates_for_address(addr)
        if coords and coords != (0.0, 0.0):
            coordinates.append(coords)
        else:
            print(f"[Routing] Aviso: Não foi possível geocodificar o endereço: {addr}. Usando fallback no meio do mar.")
            coordinates.append((0.0, 0.0)) # Fallback extremo para não quebrar a matriz, embora vá gerar uma rota bizarra.
            
    # Remove as coordenadas zeradas (que falharam no geocode) para não quebrar a lógica real
    # Mas como as orders estão atreladas aos índices, precisamos manter o índice batendo.
    # Se falhar o CD, quebra tudo.
    if coordinates[0] == (0.0, 0.0):
        return {"error": "Falha crítica: Não foi possível geocodificar o endereço do Centro de Distribuição (Ponto Zero). Verifique o endereço."}
        
    # 2. Get Matrices
    dist_matrix, dur_matrix = await get_osrm_distance_matrix(coordinates)
    
    if not dist_matrix or not dur_matrix:
        return {"error": "Falha ao obter matrizes de distância."}

    # 3. Solve VRPTW
    vrp_solution = solve_vrp_ortools(dur_matrix)
    
    if "error" in vrp_solution:
        return vrp_solution
        
    sequence = vrp_solution["sequence"]
    
    # 4. Calculate actual totals based on sequence and matrices
    total_distance_meters = 0.0
    total_duration_seconds = 0.0
    
    # Get Route Geometry and Steps using the optimized sequence
    ordered_coordinates = [coordinates[i] for i in sequence]
    route_details = await get_osrm_route(ordered_coordinates)
    
    # Extrai os steps se disponíveis (em inglês por padrão no OSRM público)
    steps = []
    geometry = {}
    if route_details and "legs" in route_details and len(route_details["legs"]) > 0:
        geometry = route_details.get("geometry", {})
        for leg in route_details["legs"]:
            for step in leg.get("steps", []):
                type_m = step.get("maneuver", {}).get("type", "")
                modifier_m = step.get("maneuver", {}).get("modifier", "")
                name_m = step.get("name", "")
                exit_m = step.get("maneuver", {}).get("exit", None)
                
                instruction = ""
                if type_m == "turn":
                    if modifier_m == "right":
                        instruction = f"Vire à direita {('na ' + name_m) if name_m else ''}".strip()
                    elif modifier_m == "left":
                        instruction = f"Vire à esquerda {('na ' + name_m) if name_m else ''}".strip()
                    elif modifier_m == "slight right":
                        instruction = f"Vire levemente à direita {('na ' + name_m) if name_m else ''}".strip()
                    elif modifier_m == "slight left":
                        instruction = f"Vire levemente à esquerda {('na ' + name_m) if name_m else ''}".strip()
                    else:
                        instruction = f"Vire {('em ' + name_m) if name_m else ''}".strip()
                elif type_m == "continue":
                    instruction = f"Continue {('na ' + name_m) if name_m else ''}".strip()
                elif type_m == "depart":
                    instruction = "Siga"
                elif type_m == "arrive":
                    instruction = "Chegada ao destino"
                elif type_m == "roundabout":
                    if exit_m:
                        instruction = f"Na rotatória, pegue a saída {exit_m} {('para ' + name_m) if name_m else ''}".strip()
                    else:
                        instruction = f"Entre na rotatória {('e siga para ' + name_m) if name_m else ''}".strip()
                else:
                    instruction = f"Siga {('na ' + name_m) if name_m else ''}".strip()
                
                steps.append({
                    "instruction": instruction,
                    "distance_meters": step.get("distance", 0.0)
                })
    
    # sequence includes returning to depot, if you don't want return trip, iterate until len-1
    for i in range(len(sequence) - 1):
        from_node = sequence[i]
        to_node = sequence[i+1]
        total_distance_meters += dist_matrix[from_node][to_node]
        total_duration_seconds += dur_matrix[from_node][to_node]
        
    return {
        "sequence": sequence,
        "sequence_coordinates": ordered_coordinates,
        "total_distance_km": round(total_distance_meters / 1000.0, 2),
        "total_eta_minutes": round(total_duration_seconds / 60.0, 2),
        "geometry": geometry,
        "steps": steps
    }
