# Utilisation d'une image Python légère
FROM python:3.12-slim

# Définition du répertoire de travail
WORKDIR /app

# Copie des fichiers de dépendances et installation
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie du reste du code source
COPY . .

# Cloud Run injecte le port via la variable d'environnement PORT
ENV PORT=8080

# Commande pour lancer Streamlit sur le bon port
CMD ["sh", "-c", "streamlit run src/ui/app.py --server.port=$PORT --server.address=0.0.0.0"]