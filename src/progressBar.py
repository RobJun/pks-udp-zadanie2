# Print iterations progress
#https://stackoverflow.com/questions/3173320/text-progress-bar-in-the-console
def printProgressBar (iteration, total, prefix = '', suffix = ''):
    percent = ("{0:.3f}").format(100 * (iteration / total))
    filledLength = int(50 * iteration // total)
    bar = '█' * filledLength + '-' * (50- filledLength)
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end = "\r")
    # Print New Line on Complete
    if iteration == total: 
        print()