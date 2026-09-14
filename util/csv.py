import matplotlib.pyplot as plt
import numpy as np
import os


def fill_csv(csv_dict: dict[str, list[str]], params: dict[str, str]):
    """Fill in parameters within a csv dict."""
    csv_len = 0 if len(csv_dict.values()) == 0 else len(list(csv_dict.values())[0])
    for key in csv_dict.keys():
        if key in list(params.keys()):
            csv_dict[key].append(params[key])
            del params[key]
        else:
            csv_dict[key].append('')
    for key in params.keys():
        csv_dict[key] = ['']*csv_len + [params[key]]
    return csv_dict

def save_csv(data: list[list[str]], filename: str):
        # Set up output file without overwriting previous runs
        fn = filename
        filenum = 1
        while os.path.exists(f'D:/20260813_chamber/DataCollect/{fn}.csv'):
            filenum += 1
            fn = f'{filename} ({filenum})'
        np.savetxt(f'D:/20260813_chamber/DataCollect/{fn}.csv', data, delimiter=', ', fmt='%s')

def save_csv_from_dict(data: dict[str, list[str]], filename: str):
    keys = list(data.keys())
    lines = len(data[keys[0]])
    data_arr = [keys]
    for line_num in range(lines):
        data_arr.append([data[key][line_num] for key in keys])
    save_csv(data_arr, filename)

def save_csv_from_lists(sweep: list[float], data: list[list[float]],
                 data_names: list[str], filename: str, precision: int = 4):
    """Generate a .csv file in the 'results' folder containing the given \
       sweep data.

    Args:
        sweep: List of frequency or time points in the sweep
        data: Sweep data to be saved. Passed in as a list of lists to
              accomodate multiple rx data sets.
        data_names: List of names for each data set
        filename: Name of .csv file
    """
    try:
        for set in data:
            assert len(sweep) == len(set)
    except Exception as e:
        print(f'ERROR: {len(sweep)} != {len(set)}')
        raise e
    try:
        assert len(data) + 1 == len(data_names)
    except Exception as e:
        print(f'ERROR: {len(data)+1} != {len(data_names)}')
        raise e
    output = [data_names]
    for i in range(len(sweep)):
        point = [round(sweep[i], precision)]
        for j in range(len(data)):
            point.append(round(data[j][i], precision))
        output.append(point)

    save_csv(output, filename)

def combine_csv_files(in_fns: list[str], out_fn: str):
    with open(out_fn, 'w') as outfile:
        for fn in in_fns:
            with open(fn, 'r') as infile:
                for line in infile.readlines():
                    outfile.write(line)

def plot_csv(csv: str | list[str], line_labels: list[str], title: str,
             y_min: float, y_max: float,
             xlabel: str = 'Frequency (MHz)', ylabel: str = 'Power (dBm)',
             figure: plt.Figure | None = None,
             subplot_pos: int | None = None) -> plt.Figure:
    if type(csv) is str:
        csv = [csv]
    
    if figure is not None:
        fig = figure
    else:
        fig = plt.figure()
        fig.suptitle(title)
    p = fig.add_subplot() if subplot_pos is None \
        else fig.add_subplot(subplot_pos)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    p.grid(True)
    
    for n in range(len(csv)):
        try:
            with open(csv[n], 'r') as infile:
                data = infile.readlines()
                num_lines = len(data[0].split(','))
                output = [[] for _ in range(num_lines)]

                for line_num in range(len(data)):
                    line = data[line_num].strip().split(',')
                    line_data = []
                    for item in line:
                        try:
                            line_data.append(float(item))
                        except:
                            # line_data.append(item)
                            pass
                    for i in range(len(line_data)):
                        output[i].append(line_data[i])

                output[0] = [x/1e6 for x in output[0]]

                p.set_ylim(y_min, y_max)
                p.set_xlim(output[0][0], output[0][-1])
                # for i in range(1, len(output)):
                p.plot(output[0], output[3], label=line_labels[n])
                p.legend(loc="upper right")
        except FileNotFoundError:
            print(f"Error: '{csv[n]}' not found!", flush=True)

    return fig
