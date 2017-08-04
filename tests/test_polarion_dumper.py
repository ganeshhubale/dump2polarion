# encoding: utf-8
# pylint: disable=missing-docstring,redefined-outer-name,no-self-use

import os
import io
import shutil
import pytest

from mock import patch

from tests import conf

from dump2polarion.exceptions import Dump2PolarionException
from dump2polarion import dumper_cli
from dump2polarion import dbtools


class TestDumperCLI(object):
    def test_get_args(self):
        args = dumper_cli.get_args(['-i', 'dummy', '-t', 'testrun_id'])
        assert args.input_file == 'dummy'
        assert args.output_file is None
        assert args.testrun_id == 'testrun_id'
        assert args.config_file is None
        assert args.no_submit is False
        assert args.user is None
        assert args.password is None
        assert args.force is False
        assert args.log_level is None

    def test_testrun_id_match(self):
        args = dumper_cli.get_args(['-i', 'dummy', '-t', '5_8_0_17'])
        found = dumper_cli.get_testrun_id(args, '5_8_0_17')
        assert found == '5_8_0_17'

    def test_testrun_id_nomatch(self):
        args = dumper_cli.get_args(['-i', 'dummy', '-t', '5_8_0_17'])
        with pytest.raises(Dump2PolarionException):
            dumper_cli.get_testrun_id(args, '5_8_0_18')

    def test_testrun_id_force(self):
        args = dumper_cli.get_args(['-i', 'dummy', '-t', '5_8_0_18', '--force'])
        found = dumper_cli.get_testrun_id(args, '5_8_0_17')
        assert found == '5_8_0_18'

    def test_testrun_id_missing(self):
        args = dumper_cli.get_args(['-i', 'dummy'])
        with pytest.raises(Dump2PolarionException):
            dumper_cli.get_testrun_id(args, None)

    def test_submit_if_ready_noxml(self, config_prop):
        args = dumper_cli.get_args(['-i', 'submit.txt'])
        with patch('dump2polarion.submit_and_verify', return_value=True):
            retval = dumper_cli.submit_if_ready(args, config_prop)
        assert retval is None

    def test_submit_if_ready_nosubmit(self, tmpdir, config_prop):
        xml_content = '<testcases foo=bar>'
        xml_file = tmpdir.join('submit_nosubmit.xml')
        xml_file.write(xml_content)
        args = dumper_cli.get_args(['-i', str(xml_file), '--no-submit'])
        with patch('dump2polarion.submit_and_verify', return_value=True):
            retval = dumper_cli.submit_if_ready(args, config_prop)
        assert retval == 0

    def test_submit_if_ready_failed(self, tmpdir, config_prop):
        xml_content = '<testcases foo=bar>'
        xml_file = tmpdir.join('submit_failed.xml')
        xml_file.write(xml_content)
        args = dumper_cli.get_args(['-i', str(xml_file)])
        with patch('dump2polarion.submit_and_verify', return_value=False):
            retval = dumper_cli.submit_if_ready(args, config_prop)
        assert retval == 2

    @pytest.mark.parametrize('tag', ('testsuites', 'testcases'))
    def test_submit_if_ready_ok(self, tmpdir, config_prop, tag):
        xml_content = '<{} foo=bar>'.format(tag)
        xml_file = tmpdir.join('submit_ready.xml')
        xml_file.write(xml_content)
        args = dumper_cli.get_args(['-i', str(xml_file)])
        with patch('dump2polarion.submit_and_verify', return_value=True):
            retval = dumper_cli.submit_if_ready(args, config_prop)
        assert retval == 0

    @pytest.mark.parametrize('submit', (True, False), ids=('submit', 'nosubmit'))
    def test_main_valid(self, tmpdir, config_e2e, submit):
        input_file = os.path.join(conf.DATA_PATH, 'workitems_ids.csv')
        output_file = tmpdir.join('out.xml')
        args = ['-i', input_file, '-o', str(output_file), '-c', config_e2e]
        if not submit:
            args.append('-n')

        with patch('dump2polarion.submit_and_verify', return_value=True),\
                patch('dump2polarion.dumper_cli.init_log'):
            retval = dumper_cli.main(args)
        assert retval == 0

        golden_output = 'complete_transform.xml'
        with io.open(os.path.join(conf.DATA_PATH, golden_output), encoding='utf-8') as golden_xml:
            parsed = golden_xml.read()
        with io.open(str(output_file), encoding='utf-8') as out_xml:
            produced = out_xml.read()
        assert produced == parsed

    def test_main_submit_ready(self):
        input_file = os.path.join(conf.DATA_PATH, 'complete_transform.xml')
        args = ['-i', input_file]

        with patch('dump2polarion.submit_and_verify', return_value=True), \
                patch('dump2polarion.dumper_cli.init_log'):
            retval = dumper_cli.main(args)
        assert retval == 0

    def test_main_submit_failed(self, tmpdir, config_e2e):
        input_file = os.path.join(conf.DATA_PATH, 'workitems_ids.csv')
        output_file = tmpdir.join('out.xml')
        args = ['-i', input_file, '-o', str(output_file), '-c', config_e2e]

        with patch('dump2polarion.submit_and_verify', return_value=False), \
                patch('dump2polarion.dumper_cli.init_log'):
            retval = dumper_cli.main(args)
        assert retval == 2

        golden_output = 'complete_transform.xml'
        with io.open(os.path.join(conf.DATA_PATH, golden_output), encoding='utf-8') as golden_xml:
            parsed = golden_xml.read()
        with io.open(str(output_file), encoding='utf-8') as out_xml:
            produced = out_xml.read()
        assert produced == parsed

    # pylint: disable=too-many-locals,protected-access
    def test_main_submit_db(self, tmpdir, config_e2e):
        orig_db_file = os.path.join(conf.DATA_PATH, 'workitems_ids.sqlite3')
        db_file = os.path.join(str(tmpdir), 'workitems_copy.sqlite3')
        shutil.copy(orig_db_file, db_file)

        output_file = tmpdir.join('out.xml')
        args = ['-i', db_file, '-o', str(output_file), '-c', config_e2e]

        with patch('dump2polarion.submit_and_verify', return_value=True), \
                patch('dump2polarion.dumper_cli.init_log'):
            retval = dumper_cli.main(args)
        assert retval == 0

        golden_output = 'complete_transform.xml'
        with io.open(os.path.join(conf.DATA_PATH, golden_output), encoding='utf-8') as golden_xml:
            parsed = golden_xml.read()
        with io.open(str(output_file), encoding='utf-8') as out_xml:
            produced = out_xml.read()
        assert produced == parsed

        conn = dbtools._open_sqlite(db_file)
        cur = conn.cursor()
        select = "SELECT count(*) FROM testcases WHERE exported == 'yes'"
        cur.execute(select)
        num = cur.fetchone()
        conn.close()
        assert num[0] == 13