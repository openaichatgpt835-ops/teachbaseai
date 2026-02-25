cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml exec -T backend python -m pip install "python-jose[cryptography]==3.3.0"
docker compose -f docker-compose.prod.yml exec -T backend python -c "import jose; print(jose.__version__)"
