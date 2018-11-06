"""Perform a static analysis for python modules

This module works together with a change in Gerrit Code Review
"""
from __future__ import print_function

import sys
import os

from bash import bash

MINIMUM_SCORE_PER_FILE = 9
VERDICT = '/tmp/VERDICT'


def python_static_analysis(repository, print_results=False):
    """Perform a static analysis

    This function perform a static analysis to python modules with pylint
    :param repository: the repository to perform the analysis
    :param print_results: print the results of the static analysis performed
    :return:
        - PASS: when all the python modules in a change has the same or greater
                than the minimum score allowed
        - FAIL: when some python module has the score lower than the minimum
                score allowed
        - NOT_RUN: if there is not python files in the Gerrit patch
    """
    sha = bash('git -C {} rev-parse HEAD'.format(repository)).stdout
    git_files = bash('git -C {} diff-tree --no-commit-id --name-only -r {}'
                     .format(repository, sha)).stdout.split()
    python_files = []

    for f in git_files:
        if '.py' in f:
            python_files.append(f)

    if python_files:
        # pylint variables
        pylint_config = '{}/{}'.format(repository, '.pylintrc')
        pylint_cmd = ('--rcfile={} --jobs=2  --score=yes --reports=no '
                      '--output-format=text').format(pylint_config)

        pylint_scores = {}
        status = None

        # iterating over the python files to get the results
        for git_file in git_files:
            file_path = os.path.join(repository, git_file)
            file_score = bash('pylint {} {}'.format(pylint_cmd, file_path))
            file_score = file_score.stdout.split()[-2:][:1][0].replace(
                '/10', '').replace(',', '')

            # compare the results with the minimum score
            if float(file_score) < MINIMUM_SCORE_PER_FILE:
                # this mean that the file does not complies with the rules
                status = 'FAIL'
            elif float(file_score) >= MINIMUM_SCORE_PER_FILE:
                status = 'PASS'
            tmp_dict = {git_file: {'score': file_score, 'status': status}}
            pylint_scores.update(tmp_dict)

        if print_results in ['TRUE', 'True']:
            print(pylint_scores)
        else:
            # check if there were any score lower than minimum score acceptable
            for git_file, results in pylint_scores.items():
                if results['status'] == 'FAIL':
                    with open(VERDICT, 'w') as verdict:
                        verdict.write('FAIL')
                    return

            with open(VERDICT, 'w') as verdict:
                verdict.write('PASS')
    else:
        with open(VERDICT, 'w') as verdict:
            verdict.write('NOT_RUN')


if __name__ == '__main__':
    try:
        python_static_analysis(sys.argv[1], sys.argv[2])
    except IndexError:
        python_static_analysis(sys.argv[1])
