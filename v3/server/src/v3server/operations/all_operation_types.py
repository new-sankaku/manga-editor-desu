"""操作の一覧。正本を変える手段はここに並べた操作だけ。"""


from typing import Annotated, Union

from pydantic import Field, TypeAdapter

from v3server.operations.image_file_operations import RegisterImage
from v3server.operations.name_proposal_operations import (
    ApplyNameProposal,
    RestoreNameSnapshot,
    SetNameProposalStatus,
    SubmitNameProposal,
)
from v3server.operations.work_setting_operations import (
    AllowDestination,
    RecordFindingReaction,
    SetMember,
    SetThreshold,
    SetWorkSettings,
)
from v3server.operations.work_tree_operations import (
    AddEpisode,
    AddPage,
    AddPanel,
    AddVolume,
    AssignPage,
    SetRemoved,
    UpdateEpisode,
    UpdatePage,
    UpdatePanel,
)

Op = Annotated[
    Union[
        SetWorkSettings,
        SetMember,
        AllowDestination,
        SetThreshold,
        RecordFindingReaction,
        AddVolume,
        AddEpisode,
        UpdateEpisode,
        AddPage,
        AssignPage,
        AddPanel,
        UpdatePanel,
        UpdatePage,
        SetRemoved,
        SubmitNameProposal,
        SetNameProposalStatus,
        ApplyNameProposal,
        RestoreNameSnapshot,
        RegisterImage,
    ],
    Field(discriminator="type"),
]

op_adapter: TypeAdapter[Op] = TypeAdapter(Op)
