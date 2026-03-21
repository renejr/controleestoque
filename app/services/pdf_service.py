import io
import datetime
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle

def generate_manifest_pdf(manifest_data: dict, vehicle_data: dict) -> bytes:
    """
    Gera o PDF do Romaneio de Entrega com Planta Baixa e Checklist.
    Retorna os bytes do PDF gerado.
    """
    buffer = io.BytesPath() if hasattr(io, 'BytesPath') else io.BytesIO() # Trata StringIO/BytesIO
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # --- Cores por Parada (Para diferenciar no mapa de carga) ---
    stop_colors = [
        colors.red, colors.blue, colors.green, colors.orange,
        colors.purple, colors.cyan, colors.magenta, colors.brown,
        colors.darkred, colors.darkblue
    ]

    # --- Cabeçalho ---
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, height - 50, "ROMANEIO DE CARGA E ENTREGA TÁTICO")
    
    c.setFont("Helvetica", 12)
    c.drawString(50, height - 75, f"Data/Hora: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}")
    c.drawString(50, height - 95, f"Veículo: {vehicle_data.get('plate', 'N/A')} - {vehicle_data.get('model', 'N/A')}")
    c.drawString(50, height - 115, f"Romaneio ID: {manifest_data.get('romaneio_id', 'N/A')}")
    
    total_stops = len(manifest_data.get('optimized_orders', []))
    c.drawString(300, height - 95, f"Total de Paradas: {total_stops}")
    c.drawString(300, height - 115, f"Distância Estimada: {manifest_data.get('total_distance_km', 0):.1f} km")

    # --- Planta Baixa do Baú (Visual Packing Plan) ---
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, height - 160, "Plano de Carga (Visão Superior)")

    # Desenhar o Baú do Caminhão
    box_x = 50
    box_y = height - 420
    box_w = 200
    box_h = 250
    
    c.setStrokeColor(colors.black)
    c.setLineWidth(2)
    c.rect(box_x, box_y, box_w, box_h, fill=0) # Baú vazio
    
    # Calcular escala do desenho
    real_truck_w = vehicle_data.get('compartment_width', 200) # cm
    real_truck_l = vehicle_data.get('compartment_length', 400) # cm
    
    scale_w = box_w / (real_truck_w if real_truck_w > 0 else 1)
    scale_l = box_h / (real_truck_l if real_truck_l > 0 else 1)
    scale = min(scale_w, scale_l) # Mantém a proporção

    # Desenhar os itens dentro do baú
    items_packed = manifest_data.get('fitted_items', [])
    
    # Mapear Parada -> Cor e Parada -> ID do Pedido
    order_stop_map = {}
    for idx, order in enumerate(manifest_data.get('optimized_orders', [])):
        order_stop_map[order['order_id']] = idx + 1 # Parada 1, 2, 3...

    c.setLineWidth(1)
    for item in items_packed:
        pos = item.get('position', {})
        dim = item.get('dimensions', {})
        order_id = item.get('order_id', '')
        
        # Pega a cor baseada no número da parada (ou cinza se não achar)
        stop_num = order_stop_map.get(order_id, 0)
        item_color = stop_colors[(stop_num - 1) % len(stop_colors)] if stop_num > 0 else colors.lightgrey
        
        # Eixo 3D -> 2D (Top Down)
        rx = pos.get('x', 0)
        ry = pos.get('y', 0) # Altura do chão (Altitude)
        rz = pos.get('z', 0) # Profundidade
        
        rw = item.get('width', dim.get('width', 0))
        rl = item.get('depth', dim.get('length', 0))
        
        px = box_x + (rx * scale)
        py = box_y + box_h - (rz * scale) - (rl * scale) # Inverte o Y do PDF (0 é embaixo)
        pw = rw * scale
        pl = rl * scale
        
        # Só desenha se tiver tamanho
        if pw > 0 and pl > 0:
            c.setFillColor(item_color)
            c.setStrokeColor(colors.white if ry > 0 else colors.black) # Contraste se empilhado
            
            # Se a caixa estiver empilhada (y > 0), desenha uma "sombra"
            if ry > 0:
                c.rect(px+1, py-1, pw, pl, fill=1, stroke=0)
                
            c.rect(px, py, pw, pl, fill=1, stroke=1)
            
            # Texto da Parada dentro da caixa
            if pw > 15 and pl > 10:
                c.setFillColor(colors.white)
                c.setFont("Helvetica-Bold", 8)
                c.drawString(px + 2, py + (pl/2) - 3, f"P{stop_num}")

    # --- Legenda de Cores ---
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(300, height - 160, "Legenda de Paradas:")
    
    leg_y = height - 180
    for idx, order in enumerate(manifest_data.get('optimized_orders', [])):
        stop_num = idx + 1
        color = stop_colors[(stop_num - 1) % len(stop_colors)]
        c.setFillColor(color)
        c.rect(300, leg_y, 10, 10, fill=1, stroke=1)
        c.setFillColor(colors.black)
        c.setFont("Helvetica", 10)
        c.drawString(315, leg_y + 2, f"Parada {stop_num}: {order.get('customer_name', 'Cliente')} (Pedido #{order['order_id'][:5]})")
        leg_y -= 15

    # --- Checklist de Entrega Tática (Tabela) ---
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, box_y - 40, "Checklist de Descarregamento (Por Parada)")
    
    table_data = [["Parada", "Cliente / Endereço", "Qtd", "Check"]]
    
    for idx, order in enumerate(manifest_data.get('optimized_orders', [])):
        stop_num = f"#{idx + 1}"
        cliente_info = f"{order.get('customer_name', '')}\n{order.get('address', '')}"
        
        # Contar itens dessa ordem que estão no caminhão
        qtd_items = sum(1 for i in items_packed if i.get('order_id') == order['order_id'])
        
        table_data.append([
            stop_num,
            cliente_info,
            str(qtd_items),
            "[   ]" # Quadrado para assinar
        ])

    if len(table_data) > 1:
        t = Table(table_data, colWidths=[50, 300, 50, 50])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (1, 1), (1, -1), 'LEFT'), # Alinha endereço à esquerda
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ]))
        
        # Desenha a tabela na página
        t.wrapOn(c, width, height)
        t.drawOn(c, 50, box_y - 70 - (len(table_data)*20))

    # --- Rodapé para Assinatura ---
    c.setFont("Helvetica", 10)
    c.drawString(50, 50, "Assinatura do Motorista: ___________________________________________")
    c.drawString(350, 50, "Assinatura do Conferente: ___________________________________________")

    c.save()
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
