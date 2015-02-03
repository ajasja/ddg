#!/usr/bin/python

import sys
import os
import argparse
import cPickle as pickle
import sqlite3

import analysis.stats as stats
from alanine_scanning import parse_mutations_file

pickle_name = os.path.join('data', 'job_dict.pickle')
global_analysis_output_dir = 'analysis_output'

def parse_db_output(db_output_file, ddg_data, score_fxns):
    query = 'SELECT ddG.resNum, ddg.mutated_to_name3, ddg.ddG_value, ' \
    'structures.tag, residue_pdb_identification.residue_number, ' \
    'residue_pdb_identification.chain_id, residues.name3, batches.description, batches.name ' \
    'FROM ddg INNER JOIN structures ON structures.struct_id=ddg.struct_id ' \
    'INNER JOIN residue_pdb_identification ON residue_pdb_identification.struct_id=structures.struct_id ' \
    'AND residue_pdb_identification.residue_number=ddg.resNum ' \
    'INNER JOIN residues ON residues.struct_id=structures.struct_id AND residues.resNum=ddg.resNum ' \
    'INNER JOIN batches ON batches.batch_id=structures.batch_id'

    conn = sqlite3.connect(db_output_file)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    for rosetta_resnum, mutated_to, ddg_calc, tag, pdb_resnum, chain, original_name3, description, tanja_id in c.execute(query):
        pdb_id = tag.split('_')[0]
        assert( len(pdb_id) == 4 )
        if tanja_id not in ddg_data:
            ddg_data[tanja_id] = {}
        ddg_data[tanja_id][description] = ddg_calc
        score_fxns.add(description)

    conn.close()
    return (ddg_data, score_fxns)

if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('output_dirs',
                        nargs='*',
                        help = 'Output directories')
    args = parser.parse_args()

    for output_dir in args.output_dirs:

        analysis_output_dir = os.path.join(global_analysis_output_dir, os.path.basename(output_dir))
        if not os.path.isdir(analysis_output_dir):
            os.makedirs(analysis_output_dir)

        assert( os.path.isdir(output_dir) )
        job_pickle_file = os.path.join(
            output_dir, pickle_name
        )
        
        with open(job_pickle_file,'r') as p:
            job_dict = pickle.load(p)

        db_output_files = []
        for job_dir in job_dict:
            job_dir = os.path.join(output_dir, job_dir)
            db_output_file = os.path.join(job_dir, 'rosetta_output.db3')
            if os.path.isfile(db_output_file):
                db_output_files.append(db_output_file)

        print 'Found %d output dbs (%d expected)' % (len(db_output_files), len(job_dict))

        score_fxns = set()
        ddg_data = {}
        for db_output_file in db_output_files:
            ddg_data, score_fxns = parse_db_output(db_output_file, ddg_data, score_fxns)

        mutations_data = parse_mutations_file()

        for mut in mutations_data.values():
            for i, tanja_id in enumerate(mut.tanja_id_list):
                if tanja_id not in ddg_data:
                    ddg_data[tanja_id] = {}
                ddg_data[tanja_id]['ddg_obs'] = mut.ddg_obs_list[i]
                ddg_data[tanja_id]['tanja_ddg_calc'] = mut.ddg_calc_list[i]

        score_fxns = sorted(list(score_fxns))
        score_fxns.insert(0, 'tanja_ddg_calc')
        score_fxns.insert(0, 'ddg_obs')

        # Write output CSV and create data lists for further analysis
        data_ids = []
        data_points = [[] for x in xrange(len(score_fxns))]
        with open(
            os.path.join(analysis_output_dir,
                         'results-%s.csv' % os.path.basename(output_dir)),
            'w'
        ) as f:
            f.write('ID')
            for score_fxn in score_fxns:
                f.write(',%s' % score_fxn)
            f.write('\n')
            for tanja_id in sorted( ddg_data.keys() ):
                f.write('%s' % tanja_id)
                data_is_complete = True
                for score_fxn in score_fxns:
                    if score_fxn in ddg_data[tanja_id]:
                        f.write(',%.6f' % ddg_data[tanja_id][score_fxn])
                    else:
                        data_is_complete = False
                        f.write(',NA')
                if data_is_complete:
                    data_ids.append(tanja_id)
                    for i, score_fxn in enumerate(score_fxns):
                        data_points[i].append(ddg_data[tanja_id][score_fxn])
                f.write('\n')

        # for i, i_score_fxn in enumerate(score_fxns):
        i = 0
        i_score_fxn = score_fxns[0]
        for j, j_score_fxn in enumerate(score_fxns):
            if i == j:
                continue

            print i_score_fxn, 'vs', j_score_fxn
            dataset_stats = stats._get_xy_dataset_statistics(
                data_points[i], data_points[j]
            )

            stats_str = stats.format_stats_for_printing(dataset_stats)
            with open(os.path.join(analysis_output_dir, '%s-stats.txt' % os.path.basename(output_dir)), 'a') as f:
                f.write('%s vs %s\n' % (i_score_fxn, j_score_fxn) )
                f.write(stats_str)
                f.write('\n\n')
            print stats_str
            print

            table_for_plot = []
            for pt_id, pt_i, pt_j in zip(data_ids, data_points[i], data_points[j]):
                table_for_plot.append(dict(ID = pt_id, Experimental = pt_i, Predicted = pt_j))

            stats.plot(
                table_for_plot,
                os.path.join(
                    analysis_output_dir,
                    '%s-%s_vs_%s.pdf' % (os.path.basename(output_dir), score_fxns[i], score_fxns[j])
                ),
                stats.RInterface.correlation_coefficient_gplot
            )
