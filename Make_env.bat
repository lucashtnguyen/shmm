call conda remove -n shmm --all --yes
call conda create --name=shmm --channel=conda-forge python=3.6 geopandas pandas numpy seaborn pytest --yes
call activate shmm
REM call pip install wheels\numpy-1.13.3-cp35-none-win_amd64.whl
REM if the exe ends up being too big we will need to exclude mpl
REM really we are not using it for much in this lib.
REM call conda install --yes --channel=conda-forge --file=requirements.txt
call pip install https://github.com/lucashtnguyen/hymo/archive/0.1.1b.zip
call deactivate
pause

