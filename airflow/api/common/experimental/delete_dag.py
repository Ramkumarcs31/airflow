# -*- coding: utf-8 -*-
#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
"""Delete DAGs APIs."""
import os

from sqlalchemy import or_

from airflow import models
from airflow.models import TaskFail, DagModel
from airflow.utils.db import provide_session
from airflow.exceptions import DagFileExists, DagNotFound


@provide_session
def delete_dag(dag_id, keep_records_in_log=True, session=None):
    """
    :param dag_id: the dag_id of the DAG to delete
    :param keep_records_in_log: whether keep records of the given dag_id
        in the Log table in the backend database (for reasons like auditing).
        The default value is True.
    :param session: session used
    :return count of deleted dags
    """
    dag = session.query(DagModel).filter(DagModel.dag_id == dag_id).first()
    if dag is None:
        raise DagNotFound("Dag id {} not found".format(dag_id))

    if dag.get_local_fileloc() and os.path.exists(dag.get_local_fileloc()):
        raise DagFileExists("Dag id {} is still in DagBag. "
                            "Remove the DAG file first: {}".format(dag_id, dag.get_local_fileloc()))

    count = 0

    # noinspection PyUnresolvedReferences,PyProtectedMember
    for model in models.base.Base._decl_class_registry.values():  # pylint: disable=protected-access
        if hasattr(model, "dag_id"):
            if keep_records_in_log and model.__name__ == 'Log':
                continue
            cond = or_(model.dag_id == dag_id, model.dag_id.like(dag_id + ".%"))
            count += session.query(model).filter(cond).delete(synchronize_session='fetch')
    if dag.is_subdag:
        parent_dag_id, task_id = dag_id.rsplit(".", 1)
        for model in models.DagRun, TaskFail, models.TaskInstance:
            count += session.query(model).filter(model.dag_id == parent_dag_id,
                                                 model.task_id == task_id).delete()

    return count
