from py3dbp import Packer, Bin, Item

def calculate_packing(vehicle, products_list: list):
    """
    Executa o algoritmo de Bin Packing (Cubagem) para calcular
    se uma lista de produtos cabe dentro do baú de um veículo.
    
    :param vehicle: Instância do modelo Vehicle (banco de dados)
    :param products_list: Lista de dicionários, onde cada item representa uma unidade física de um Produto.
                          Ex: [{'id': 'prod_1', 'name': 'TV', 'width': 100, 'height': 60, 'length': 20, 'weight': 15}, ...]
    :return: Dicionário com o relatório de cubagem.
    """
    packer = Packer()

    # 1. Adiciona o Veículo como o Bin (Caixa principal)
    # py3dbp usa (name, width, height, depth, max_weight)
    packer.add_bin(Bin(
        str(vehicle.license_plate),
        vehicle.compartment_width,
        vehicle.compartment_height,
        vehicle.compartment_length,
        vehicle.max_weight_capacity
    ))

    # 2. Adiciona os Produtos como Items
    # py3dbp usa (name, width, height, depth, weight)
    names_map = {} # Mapa para lembrar os nomes
    
    for index, p in enumerate(products_list):
        base_id = str(p['id'])
        # Cria um ID único para a unidade física (para não misturar se houver produtos iguais)
        item_id = f"{base_id}_{index}"
        
        # Guarda o nome real associado ao ID base
        names_map[base_id] = p.get('name', f"Produto [{base_id[:8]}]")
        
        packer.add_item(Item(
            item_id,
            p['width'],
            p['height'],
            p['length'],
            p['weight']
        ))

    # 3. Executa a mágica (Calcula o empacotamento)
    packer.pack()

    # 4. Extrai e formata os resultados
    # Como só adicionamos 1 Bin (o veículo), pegamos o primeiro resultado
    b = packer.bins[0]
    
    total_weight_used = 0.0
    total_volume_used = 0.0

    fitted_items = []
    for item in b.items:
        # Precisamos das dimensões reais após a rotação!
        rot_dim = item.get_dimension()
        
        # Extrai o base_id separando pelo '_'
        raw_id = str(item.name)
        base_id = raw_id.split('_')[0]

        fitted_items.append({
            "item_id": raw_id,
            "name": names_map.get(base_id, "Desconhecido"), # A CEREJA DO BOLO AQUI
            "width": float(rot_dim[0]),   # Eixo X (Largura rodada)
            "height": float(rot_dim[1]),  # Eixo Y (Altura rodada)
            "depth": float(rot_dim[2]),   # Eixo Z (Comprimento rodado)
            "position": {
                "x": float(item.position[0]),
                "y": float(item.position[1]), # Altura do empilhamento
                "z": float(item.position[2])
            },
            "rotation_type": item.rotation_type,
            "weight": float(item.weight)
        })
        total_weight_used += float(item.weight)
        total_volume_used += float(item.get_volume())

    unfitted_items = []
    for item in b.unfitted_items:
        unfitted_items.append({
            "item_id": item.name,
            "weight": float(item.weight),
            "reason": "Capacidade de peso excedida ou falta de espaço físico no baú."
        })

    # Calcula percentuais
    max_vol = vehicle.compartment_width * vehicle.compartment_height * vehicle.compartment_length
    vol_percentage = (total_volume_used / max_vol) * 100 if max_vol > 0 else 0
    weight_percentage = (total_weight_used / vehicle.max_weight_capacity) * 100 if vehicle.max_weight_capacity > 0 else 0

    return {
        "vehicle_plate": vehicle.license_plate,
        "metrics": {
            "total_weight_used_kg": round(total_weight_used, 2),
            "weight_utilization_percent": round(weight_percentage, 2),
            "total_volume_used_cm3": round(total_volume_used, 2),
            "volume_utilization_percent": round(vol_percentage, 2)
        },
        "fitted_items_count": len(fitted_items),
        "unfitted_items_count": len(unfitted_items),
        "fitted_items": fitted_items,
        "unfitted_items": unfitted_items
    }