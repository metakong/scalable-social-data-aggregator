.PHONY: init-env

init-env:
	@if [ ! -f .env ]; then \
		echo "Creating .env file from .env.example..."; \
		cp .env.example .env; \
	fi
	@echo "Checking for missing secrets in .env..."
	@if ! grep -q "SECRET_KEY=.\+" .env; then \
		SECRET_KEY_VALUE=$$(openssl rand -hex 32); \
		sed -i'' -e "s/^SECRET_KEY=.*/SECRET_KEY=$$SECRET_KEY_VALUE/" .env; \
		echo "SECRET_KEY populated."; \
	fi
	@if ! grep -q "POSTGRES_PASSWORD=.\+" .env; then \
		POSTGRES_PASSWORD_VALUE=$$(openssl rand -hex 16); \
		sed -i'' -e "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$$POSTGRES_PASSWORD_VALUE/" .env; \
		echo "POSTGRES_PASSWORD populated."; \
	fi