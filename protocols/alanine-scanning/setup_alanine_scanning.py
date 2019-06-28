#!/usr/bin/env python3

# The MIT License (MIT)
#
# Copyright (c) 2015 Kyle A. Barlow
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

"""\
The script sets up the alanine scanning step of the alanine scanning benchmark run

Usage:
    setup_alanine_scanning.py [options]...

Options:

    -o --output_directory OUTPUT_DIR
        The path to a directory where the output files to be run will be saved
    -e --extra_name EXTRA_NAME
        Extra name to appended onto the end of the job directory
    -n --number_repeats NUMBER_REPEATS
    --repack_bound
        When this option is set, residues around the mutant site in the protein complex will be repacked in the bound state
    --repack_unbound
        When this option is set, residues around the mutant site in the protein complex will be repacked in the unbound state

Authors:
    Kyle Barlow
"""

import multiprocessing
import os
from rosetta.write_run_file import process as write_run_file
import shutil
import sys
import time
import inspect
import pickle as pickle
import re
import getpass
import interfaces_defs
import rosetta.parse_settings
import argparse
from analysis.libraries import docopt
import identify_interface

input_pdb_dir_path = "../../input/pdbs/hydrogen_pdbs"
extra_name = ""  # something like _talaris if needed
mutations_file_location = "mutation_benchmark_set.csv"
rosetta_scripts_protocol = "alascan.xml"
resfile_start = "NATRO\nEX 1 EX 2 EX 3\nSTART\n"
# score_fxns = ['talaris2014', 'score12', 'interface']
# repack_score_fxns = ['talaris2014', 'score12', 'talaris2014']
score_fxns = ["talaris2014"]
repack_score_fxns = ["talaris2014"]
job_output_directory = "job_output"  # Default if not specified via options
number_scan_repeats = 1


class MutationData:
    def __init__(self, pdb_id):
        self.pdb_id = pdb_id
        self.chainres_list = []
        self.pdb_res_list = []
        self.amino_acid_list = []
        self.ddg_calc_list = []
        self.ddg_obs_list = []
        self.ddg_obs_greater_than_list = []
        self.PDBPosID_list = []
        self.chain_list = []
        self.interface_list = []
        self.new_id_list = []
        self.insertion_code_list = []
        self.id_conv = {}

        for pdb_dict in interfaces_defs.kortemme_baker_protein_protein_interfaces:
            if pdb_dict["PDBFileID"] == pdb_id:
                self.lchains = set(pdb_dict["LChains"])
                self.rchains = set(pdb_dict["RChains"])
                break

        # Load chain order
        self.chain_order = get_chain_order(pdb_id)

    def PDBPosID_to_alascan(self, PDBPosID):
        i = self.PDBPosID_list.index(PDBPosID)
        # print self.chainres_list[i][1:]
        # print self.pdb_res_list[i]
        return (three_letter_codes[self.amino_acid_list[i]], int(self.pdb_res_list[i]), self.chain_list[i])

    def add_line(self, line):
        data = [x.strip() for x in line.split(",")]
        pdb_id = data[0]
        assert pdb_id == self.pdb_id
        chain = data[2]

        if data[3] == "100B":
            pdb_res = 100
            insertion_code = "B"
        else:
            pdb_res = int(data[3])
            insertion_code = ""

        amino_acid = data[4]
        assert len(amino_acid) == 1
        ddg_calc = float(data[5])

        if data[6].startswith(">"):
            greater_than = True
            ddg_obs = float(data[6][1:])
        else:
            greater_than = False
            ddg_obs = float(data[6])

        if data[7] == "0":
            interface = False
        elif data[7] == "1":
            interface = True

        PDBPosID = data[8]
        assert PDBPosID.startswith(pdb_id)

        new_id = "%s%d" % (pdb_id, pdb_res)

        chainres = "%s%d" % (chain, pdb_res)
        assert chainres not in self.chainres_list
        self.chainres_list.append(chainres)

        self.pdb_res_list.append(pdb_res)
        self.amino_acid_list.append(amino_acid)
        self.ddg_calc_list.append(ddg_calc)
        self.ddg_obs_list.append(ddg_obs)
        self.ddg_obs_greater_than_list.append(greater_than)
        self.PDBPosID_list.append(PDBPosID)
        self.chain_list.append(chain)
        self.interface_list.append(interface)
        self.new_id_list.append(new_id)
        self.insertion_code_list.append(insertion_code)
        self.id_conv[PDBPosID] = new_id

    def in_interface(self, resnum):
        return self.interface_list[self.pdb_res_list.index(resnum)]

    def in_interface_by_id(self, PDBPosID):
        i = self.PDBPosID_list.index(PDBPosID)
        if self.interface_list[i] == 0:
            return False
        else:
            assert self.interface_list[i] == 1
            return True

    def num_chains(self):
        return len(set(self.chain_list))

    def num_residues(self):
        return len(self.pdb_res_list)

    def get_close_residues_tuple(self, PDBPosID):
        i = self.PDBPosID_list.index(PDBPosID)
        return (self.pdb_res_list[i], self.chain_list[i], self.insertion_code_list[i])

    def lchainsnumbers(self):
        # Figure out lchains order
        lchainsnumbers = ""
        for lchain in self.lchains:
            lchainsnumbers += str(self.chain_order.index(lchain) + 1)
        return lchainsnumbers

    def rchainsnumbers(self):
        # Figure out rchains order
        rchainsnumbers = ""
        for rchain in self.rchains:
            rchainsnumbers += str(self.chain_order.index(rchain) + 1)
        return rchainsnumbers

    def get_comma_chains_to_move(self):
        lchainsnumbers = self.lchainsnumbers()
        rchainsnumbers = self.rchainsnumbers()

        if "1" in lchainsnumbers:
            assert "1" not in rchainsnumbers
            chains_to_move = rchainsnumbers
        else:
            chains_to_move = lchainsnumbers

        comma_chains_to_move = ""
        for i, char in enumerate(chains_to_move):
            comma_chains_to_move += char
            if i + 1 < len(chains_to_move):
                comma_chains_to_move += ","

        return comma_chains_to_move

    def __repr__(self):
        return "%s: %d chains, %d residues" % (self.pdb_id, self.num_chains(), self.num_residues())


def get_chain_order(pdb_id):
    allchains_pdb = os.path.join(input_pdb_dir_path, "%s_0001.pdb" % pdb_id)
    last_chain = None
    chain_order = ""
    all_chains_set = set()
    with open(allchains_pdb, "r") as f:
        for line in f:
            if line.startswith("ATOM"):
                chain = line[21]
                all_chains_set.add(chain)
                if chain != last_chain:
                    last_chain = chain
                    chain_order += chain

    assert len(all_chains_set) == len(chain_order)
    return chain_order


def parse_mutations_file():
    return_dict = {}
    with open(mutations_file_location, "r") as f:
        for line in f:
            pdb_id = line.split(",")[0]
            if pdb_id == "PDB_ID":  # Skip first line
                continue
            if pdb_id not in return_dict:
                return_dict[pdb_id] = MutationData(pdb_id)
            return_dict[pdb_id].add_line(line)
    return return_dict


def make_resfile(resfile_path, mutation_datum, PDBPosID):
    # Make resfile
    mutation_info_index = mutation_datum.PDBPosID_list.index(PDBPosID)
    chain = mutation_datum.chain_list[mutation_info_index]
    pdb_res = mutation_datum.pdb_res_list[mutation_info_index]
    insertion_code = mutation_datum.insertion_code_list[mutation_info_index]

    with open(resfile_path, "w") as f:
        f.write(resfile_start)
        f.write("%d%s %s PIKAA A\n" % (pdb_res, insertion_code, chain))


def make_pack_resfile(pack_resfile_path, close_residues_list):
    with open(pack_resfile_path, "w") as f:
        f.write(resfile_start)
        for atom_resnum, atom_insertion_code, atom_chain in close_residues_list:
            f.write("%d%s %s NATAA\n" % (atom_resnum, atom_insertion_code, atom_chain))


if __name__ == "__main__":
    import pprint

    try:
        arguments = docopt.docopt(__doc__.format(**locals()))
    except Exception as e:
        print(("Failed while parsing arguments: %s." % str(e)))
        sys.exit(1)

    if arguments.get("--output_directory"):
        job_output_directory = arguments["--output_directory"][0]
        if not (os.path.exists(job_output_directory)):
            raise Exception("The specified output directory %s does not exist." % output_dir)

    if arguments.get("--extra_name"):
        extra_name = arguments["--extra_name"][0]

    if arguments.get("--number_repeats"):
        number_scan_repeats = int(arguments["--number_repeats"][0])

    if arguments.get("--repack_bound"):
        repack_bound = True
    else:
        repack_bound = False

    if arguments.get("--repack_unbound"):
        repack_unbound = True
    else:
        repack_unbound = False

    mutation_info = parse_mutations_file()
    close_residues_dict = identify_interface.get_close_residues_dict()
    # Get settings info from JSON
    settings = rosetta.parse_settings.get_dict()

    job_name = os.path.basename(inspect.getfile(inspect.currentframe())).split(".")[0] + extra_name
    output_dir = os.path.join(
        job_output_directory, "%s-%s_%s" % (time.strftime("%y%m%d"), getpass.getuser(), job_name)
    )
    output_data_dir = os.path.join(output_dir, "data")
    pdb_data_dir = os.path.join(output_data_dir, "input_pdbs")

    if not os.path.isdir(pdb_data_dir):
        os.makedirs(pdb_data_dir)

    # Copy Rosetta scripts protocol
    protocol_path = os.path.join(output_data_dir, os.path.basename(rosetta_scripts_protocol))
    shutil.copy(rosetta_scripts_protocol, protocol_path)
    protocol_relpath = os.path.relpath(protocol_path, output_dir)

    resfile_data_dir = os.path.join(output_data_dir, "resfiles")
    if not os.path.isdir(resfile_data_dir):
        os.makedirs(resfile_data_dir)

    job_dict = {}
    for pdb_id in mutation_info:
        pdb_path = os.path.join(input_pdb_dir_path, "%s_0001.pdb" % pdb_id)
        new_pdb_path = os.path.join(pdb_data_dir, os.path.basename(pdb_path))
        if not os.path.isfile(new_pdb_path):
            # Assume file is correct version to save copy time
            shutil.copy(pdb_path, new_pdb_path)
        pdb_relpath = os.path.relpath(new_pdb_path, output_dir)

        # Setup chains to move
        comma_chains_to_move = mutation_info[pdb_id].get_comma_chains_to_move()

        for score_fxn_index, score_fxn in enumerate(score_fxns):
            for PDBPosID in mutation_info[pdb_id].PDBPosID_list:
                # Make mutation resfile
                resfile_path = os.path.join(resfile_data_dir, "%s.mutation.resfile" % PDBPosID)
                if not os.path.exists(resfile_path):
                    make_resfile(resfile_path, mutation_info[pdb_id], PDBPosID)
                resfile_relpath = os.path.relpath(resfile_path, output_dir)

                # Make packing resfile
                pack_resfile_path = os.path.join(resfile_data_dir, "%s.pack.resfile" % PDBPosID)
                if not os.path.exists(pack_resfile_path):
                    close_residues_list = close_residues_dict[pdb_id][
                        mutation_info[pdb_id].get_close_residues_tuple(PDBPosID)
                    ]
                    make_pack_resfile(pack_resfile_path, close_residues_list)
                pack_resfile_relpath = os.path.relpath(pack_resfile_path, output_dir)

                sub_dict = {}
                sub_dict["-in:file:s"] = pdb_relpath

                sub_dict["-parser:protocol"] = protocol_relpath

                sub_dict["-parser:script_vars"] = [
                    "PDBPosID=%s" % PDBPosID,
                    "currentscorefxn=%s" % score_fxn,
                    "currentrepackscorefxn=%s" % repack_score_fxns[score_fxn_index],
                    "chainstomove=%s" % comma_chains_to_move,
                    "currentpackscorefxn=%s" % score_fxn,
                    "pathtoresfile=%s" % resfile_relpath,
                    "pathtopackresfile=%s" % pack_resfile_relpath,
                    "numberscanrepeats=%d" % number_scan_repeats,
                ]

                if repack_bound:
                    sub_dict["-parser:script_vars"].append("repackbound=true")
                else:
                    sub_dict["-parser:script_vars"].append("repackbound=false")

                if repack_unbound:
                    sub_dict["-parser:script_vars"].append("repackunbound=true")
                else:
                    sub_dict["-parser:script_vars"].append("repackunbound=false")

                job_dict["%s/%s/%s" % (pdb_id.upper(), PDBPosID, score_fxn)] = sub_dict

    with open(os.path.join(output_data_dir, "job_dict.pickle"), "wb") as f:
        pickle.dump(job_dict, f)

    settings["scriptname"] = "alascan_run"
    settings["appname"] = "rosetta_scripts"
    settings["rosetta_args_list"] = [
        "-parser:view",
        "-inout:dbms:mode",
        "sqlite3",
        "-inout:dbms:database_name",
        "rosetta_output.db3",
        "-no_optH",
        "true",
        "-restore_talaris_behavior", #TODO: different restore_XXXXXXXX_behaviours are needed per score function
    ]
    settings["tasks_per_process"] = 15
    settings["numjobs"] = "%d" % len(job_dict)
    settings["mem_free"] = "1.0G"
    settings["output_dir"] = output_dir

    write_run_file(settings)
    import sys
    #write a tasklist file
    with open(os.path.abspath(output_dir)+"/task.list",'w') as f:
        for i in range(len(job_dict)):
            print(f'cd {os.path.abspath(output_dir)} && {sys.executable} alascan_run.py {i}', file=f)


    print("Job files written to directory:", os.path.abspath(output_dir))

