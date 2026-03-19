from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import health, products, tenants, auth, transactions, dashboard, finance, suppliers, purchase_orders, audit_logs, oracle, vehicles, fleet, customers, sales_orders, users, suggestions, chat, subscriptions, admin
from app.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="SaaS de Gerenciamento de Estoque Modular e Whitelabel",
    version="0.1.0"
)

# Configuração de CORS para permitir o Flutter Web
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registra os routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(health.router, tags=["Health"])
app.include_router(tenants.router, prefix="/api/admin/tenants", tags=["Super Admin - Tenants"])
app.include_router(products.router, prefix="/products", tags=["Products"])
app.include_router(transactions.router, prefix="/transactions", tags=["Inventory Transactions"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
app.include_router(finance.router, prefix="/finance", tags=["Finance"])
app.include_router(suppliers.router, prefix="/suppliers", tags=["Suppliers"])
app.include_router(purchase_orders.router, prefix="/purchase-orders", tags=["Purchase Orders"])
app.include_router(audit_logs.router, prefix="/audit-logs", tags=["Audit Logs"])
app.include_router(oracle.router, prefix="/oracle", tags=["Oracle AI"])
app.include_router(vehicles.router, prefix="/vehicles", tags=["TMS - Vehicles"])
app.include_router(fleet.router, prefix="/fleet", tags=["TMS - Fleet Logistics"])
app.include_router(customers.router, prefix="/customers", tags=["Customers"])
app.include_router(sales_orders.router, prefix="/sales-orders", tags=["Sales Orders"])
app.include_router(users.router, tags=["Users"])
app.include_router(suggestions.router, tags=["Suggestions"])
app.include_router(chat.router, tags=["Chat"])
app.include_router(subscriptions.router)
app.include_router(admin.router)

@app.get("/")
async def root():
    return {"message": "Bem-vindo ao Inventory SaaS API. Acesse /docs para a documentação."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8002, reload=True)
