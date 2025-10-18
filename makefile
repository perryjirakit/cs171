d ?= 60
epsilon_max ?= 0.09
rho ?= 1e-2

.PHONY: run_project clean

run_project:
	python3 time_server.py &
	python3 network.py &
	sleep 2
	python3 client.py --d $(d) --epsilon $(epsilon_max) --rho $(rho) --csv output.csv
	@make clean

clean:
	@pkill -f time_server.py || true
	@pkill -f network.py || true

