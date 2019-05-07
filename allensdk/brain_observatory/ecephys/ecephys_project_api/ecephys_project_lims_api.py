import os

import pandas as pd

from .ecephys_project_api import EcephysProjectApi
from .lims_api_mixin import LimsApiMixin


class EcephysProjectLimsApi(EcephysProjectApi, LimsApiMixin):

    def __init__(self, **kwargs):
        super(EcephysProjectApi, self).__init__(**kwargs)

    def get_sessions(self, 
        session_ids=None, 
        workflow_states=('uploaded',),
        published=None,
        habituation=False,
        project_names=('BrainTV Neuropixels Visual Behavior', 'BrainTV Neuropixels Visual Coding')
    ):

        joins = []
        filters = []

        if project_names is not None:
            joins.append('join projects pr on pr.id = es.project_id')
            pr_names = ','.join([f"\'{pn}\'" for pn in project_names])
            filters.append(f'pr.name in ({pr_names})')

        if session_ids is not None:
            session_ids = ','.join([str(sid) for sid in session_ids])
            filters.append(f'es.id in ({session_ids})')

        if published is not None:
            filters.append(f'es.published_at is {"not" if published else ""} null')
        
        if workflow_states is not None:
            workflow_states = ','.join([f"\'{ws}\'" for ws in workflow_states])
            filters.append(f'es.workflow_state in ({workflow_states})')

        if habituation is False:
            filters.append('habituation = false')
        elif habituation is True:
            filters.append('habituation = true')

        filters = f'where {" and ".join(filters)}'
        joins = ' '.join(joins)

        query = f'select es.* from ecephys_sessions es {joins} {filters}'

        return self.select(query)

    def _get_session_nwb_paths(self, session_id):

        probe_response = self._get_probe_well_known_files([session_id], wkf_types=['EcephysLfpNwb'])
        session_response = self._get_session_well_known_files([session_id], ['EcephysNwb'])

        session_response['ecephys_probe_id'] = None
        response = (pd.concat([session_response, probe_response], sort=False)
            .reset_index()
            .drop(columns='index'))

        return response
        
    def _get_probe_well_known_files(self, session_ids=None, probe_ids=None, wkf_types=None):
        
        filters = []

        if session_ids is not None:
            session_ids = ','.join([str(sid) for sid in session_ids])
            filters.append(f'es.id in ({session_ids})')

        if probe_ids is not None:
            probe_ids = ','.join([str(pid) for pid in probe_ids])
            filters.append(f'ep.id in ({probe_ids})')

        if wkf_types is not None:
            wkf_types = ','.join([f"\'{tn}\'" for tn in wkf_types])
            filters.append(f'wkft.name in ({wkf_types})')

        filters = f'where {" and ".join(filters)}' if filters else ''

        # TODO: why does the probe analysis runs table not have a "current" field?
        query = f'''
            select wkf.storage_directory, wkf.filename, wkft.name, 
            es.id as ecephys_session_id, ep.id as ecephys_probe_id from ecephys_sessions es
            join ecephys_probes ep on ep.ecephys_session_id = es.id
            join ecephys_analysis_run_probes earp on (
                earp.ecephys_probe_id = ep.id
            )
            join well_known_files wkf on wkf.attachable_id = earp.id
            join well_known_file_types wkft on wkft.id = wkf.well_known_file_type_id
            {filters}
        '''

        response = self.select(query)
        return clean_wkf_response(response)

    def _get_session_well_known_files(self, session_ids=None, wkf_types=None):

        filters = []

        if session_ids is not None:
            session_ids = ','.join([str(sid) for sid in session_ids])
            filters.append(f'es.id in ({session_ids})')

        if wkf_types is not None:
            wkf_types = ','.join([f"\'{tn}\'" for tn in wkf_types])
            filters.append(f'wkft.name in ({wkf_types})')

        filters = f'where {" and ".join(filters)}' if filters else ''

        query = f''' 
            select wkf.storage_directory, wkf.filename, es.id as ecephys_session_id, wkft.name from ecephys_sessions es
            join ecephys_analysis_runs ear on (
                ear.ecephys_session_id = es.id
                and ear.current
            )
            join well_known_files wkf on wkf.attachable_id = ear.id
            join well_known_file_types wkft on wkft.id = wkf.well_known_file_type_id
            {filters}
        '''

        response = self.select(query)
        return clean_wkf_response(response)


def clean_wkf_response(response):
    if response.shape[0] == 0:
        return response
    response['path'] = response.apply(lambda row: os.path.join(row['storage_directory'], row['filename']), axis=1)
    response.drop(columns=['storage_directory', 'filename'], inplace=True)
    return response