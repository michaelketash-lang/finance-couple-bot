from database_manager import add_expense

print("🌱 Seeding database with dummy shared expenses...")

# Adding expenses for Michael
add_expense(merchant="Supermarket", amount=400.0, payer="Michael", split="shared", category="Food")
add_expense(merchant="Movie Tickets", amount=100.0, payer="Michael", split="shared", category="Leisure")

# Adding expenses for Ori
add_expense(merchant="Electric Bill", amount=250.0, payer="Ori", split="shared", category="Bills")

print("✅ Done! Database is ready for testing.")