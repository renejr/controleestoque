import asyncio
import sys
import os
import random
from decimal import Decimal
import uuid
from faker import Faker

# Adiciona o diretório raiz do projeto ao PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.core.database import SessionLocal
from app.models.tenant import Tenant
from app.models.product import Product
from app.models.vehicle import Vehicle
from app.models.customer import Customer
from app.models.sales_order import SalesOrder
from app.models.sales_order_item import SalesOrderItem

fake = Faker('pt_BR')

async def stress_test_data_generator():
    print("🚀 Iniciando geração de dados para Teste de Estresse Logístico...")
    
    async with SessionLocal() as db:
        try:
            # 1. Cria ou recupera um Tenant de Teste
            tenant_id = uuid.uuid4()
            
            # O Faker do pt_BR gera CNPJ formatado (ex: 53.217.064/0001-05) que tem 18 chars.
            # Nosso banco restringe a 14 chars. Vamos remover a formatação.
            raw_cnpj = fake.cnpj().replace('.', '').replace('/', '').replace('-', '')
            
            test_tenant = Tenant(
                id=tenant_id,
                name="Logistics Stress Test Corp",
                cnpj=raw_cnpj
            )
            db.add(test_tenant)
            await db.flush()
            print(f"✅ Tenant criado: {tenant_id}")

            # 2. Gera 50 Produtos (Caixas de tamanhos e pesos variados)
            print("📦 Gerando 50 Produtos...")
            products = []
            for i in range(50):
                # Simulando caixas reais (cm e kg)
                width = random.uniform(10.0, 100.0)
                height = random.uniform(10.0, 100.0)
                length = random.uniform(10.0, 100.0)
                weight = random.uniform(0.5, 30.0)
                price = Decimal(random.uniform(10.0, 500.0))
                
                prod = Product(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    name=f"Produto Teste {i+1} - {fake.word().capitalize()}",
                    sku=f"STRESS-SKU-{i+1}",
                    price=price,
                    cost_price=price * Decimal('0.5'),
                    current_stock=1000, # Estoque alto para não falhar nas vendas
                    width=round(width, 2),
                    height=round(height, 2),
                    length=round(length, 2),
                    weight=round(weight, 2)
                )
                products.append(prod)
                db.add(prod)
            
            await db.flush()

            # 3. Gera 1 Veículo (Caminhão Baú Padrão - 6 metros)
            print("🚛 Gerando Veículo de Teste (Baú 6m)...")
            vehicle = Vehicle(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                license_plate="STRESS-001",
                model_name="Caminhão Baú 6m Teste",
                tare_weight=4000.0,
                max_weight_capacity=6000.0, # 6 toneladas
                max_volume_capacity=35.0, # Aprox 35m3
                compartment_width=220.0, # 2.2m
                compartment_height=220.0, # 2.2m
                compartment_length=600.0  # 6.0m
            )
            db.add(vehicle)
            await db.flush()

            # 4. Gera 20 Clientes e 20 SalesOrders
            print("🛒 Gerando 20 Clientes e Pedidos de Venda...")
            
            # Centro de SP (Ponto base)
            base_lat = -23.5505
            base_lng = -46.6333
            
            romaneio_id = str(uuid.uuid4()) # Identificador lógico para este teste
            
            for i in range(20):
                # Gera coordenadas num raio aproximado de 20km
                lat_offset = random.uniform(-0.18, 0.18)
                lng_offset = random.uniform(-0.18, 0.18)
                
                customer = Customer(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    name=fake.company(),
                    document=fake.cnpj().replace('.', '').replace('/', '').replace('-', ''),
                    # Mockando o endereço para ter as coordenadas embutidas no log de rota
                    street=f"Rua Teste {i+1}",
                    city="São Paulo",
                    state="SP",
                )
                db.add(customer)
                await db.flush()
                
                # Criar o Pedido de Venda
                # Importante: vamos usar o campo 'notes' para guardar as coordenadas falsas
                # e o 'romaneio_id' (que não existe nativamente no modelo, vamos por na nota)
                # O status PROCESSING é o que o fleet.py busca
                order = SalesOrder(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    customer_id=customer.id,
                    status="PROCESSING",
                    notes=f"ROMANEIO:{romaneio_id}|LAT:{base_lat+lat_offset}|LNG:{base_lng+lng_offset}"
                )
                db.add(order)
                await db.flush()
                
                # Criar de 5 a 15 itens para este pedido
                num_items = random.randint(5, 15)
                total_order_amount = Decimal('0.00')
                
                selected_products = random.sample(products, num_items)
                
                for prod in selected_products:
                    qty = random.randint(1, 5)
                    item = SalesOrderItem(
                        id=uuid.uuid4(),
                        sales_order_id=order.id,
                        product_id=prod.id,
                        quantity=qty,
                        unit_price=prod.price
                    )
                    db.add(item)
                    total_order_amount += (prod.price * qty)
                
                order.total_amount = total_order_amount
                
            # Confirma tudo no banco de forma atômica
            await db.commit()
            
            print("\n" + "="*50)
            print("✅ TESTE DE ESTRESSE LOGÍSTICO CRIADO COM SUCESSO!")
            print("="*50)
            print(f"TENANT_ID para uso nos testes: {tenant_id}")
            print(f"VEÍCULO_ID gerado: {vehicle.id}")
            print(f"TOTAL DE PEDIDOS: 20 (com 5 a 15 itens cada)")
            print("="*50)
            print("Para testar a roteirização na API, os pedidos estão com status PROCESSING.")

        except Exception as e:
            await db.rollback()
            print(f"❌ Erro fatal ao gerar dados: {e}")

if __name__ == "__main__":
    asyncio.run(stress_test_data_generator())
