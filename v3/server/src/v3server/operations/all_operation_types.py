"""操作の一覧。正本を変える手段はここに並べた操作だけ。"""


from typing import Annotated

from pydantic import Field, TypeAdapter

from v3server.operations.annotation_operations import (
    AddAnnotation,
    RecordAnnotationJob,
    UpdateAnnotation,
)
from v3server.operations.book_structure_operations import AddSpread, ReorderPages, UpdateSpread
from v3server.operations.current_app_import_operations import ImportCurrentAppProject
from v3server.operations.episode_plan_operations import (
    AddForeshadowing,
    CarryOverEpisodePlan,
    SetEpisodePlan,
    UpdateForeshadowing,
)
from v3server.operations.held_change_operations import ResolveHeldChange, UndoWithHeldChanges
from v3server.operations.image_candidate_operations import AdoptImage, SetImageDiscarded
from v3server.operations.image_file_operations import (
    AddProtectedRegion,
    RegisterImage,
    SetProtectedRegionRemoved,
)
from v3server.operations.material_and_plan_operations import (
    AddMaterialEntry,
    DecideMaterialProposal,
    SetEpisodeOutline,
    SetWorkPlan,
    UpdateMaterialEntry,
)
from v3server.operations.name_proposal_operations import (
    ApplyNameProposal,
    RestoreNameSnapshot,
    SetNameProposalStatus,
    SubmitNameProposal,
)
from v3server.operations.page_item_operations import (
    AddPageItem,
    ResetAdjustments,
    SetFixed,
    UpdatePageItem,
)
from v3server.operations.panel_frame_operations import (
    AddShapePanel,
    ApplyPanelTemplate,
    MergePanels,
    RandomSplitPanel,
    SavePanelTemplate,
    SplitPanel,
)
from v3server.operations.pen_stroke_operations import (
    AddPenStrokes,
    ErasePenStrokes,
    ErasePixels,
    RemovePenStrokes,
    SetStrokeCache,
    UpdatePenStrokes,
)
from v3server.operations.psd_import_operations import ApplyPsdImport
from v3server.operations.review_operations import SetReviewStatus
from v3server.operations.row_snapshot import RestoreRows
from v3server.operations.text_and_layer_operations import (
    AddPanelLayer,
    AddTextItem,
    UpdatePanelLayer,
    UpdateTextItem,
)
from v3server.operations.text_search_and_replace import ReplaceText
from v3server.operations.text_translation_operations import SetTextTranslation, SetTextTranslationRemoved
from v3server.operations.work_setting_operations import (
    AllowDestination,
    RecordFindingReaction,
    SetAiInvolvement,
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
    SetWorkSettings | SetAiInvolvement | SetMember | AllowDestination | SetThreshold | RecordFindingReaction | AddVolume | AddEpisode | UpdateEpisode | AddPage | AssignPage | AddPanel | UpdatePanel | UpdatePage | SetRemoved | SubmitNameProposal | SetNameProposalStatus | ApplyNameProposal | RestoreNameSnapshot | RegisterImage | AddProtectedRegion | SetProtectedRegionRemoved | AddTextItem | UpdateTextItem | AddPanelLayer | UpdatePanelLayer | ResolveHeldChange | UndoWithHeldChanges | RestoreRows | SplitPanel | MergePanels | RandomSplitPanel | AddShapePanel | SavePanelTemplate | ApplyPanelTemplate | AddPageItem | UpdatePageItem | SetFixed | ResetAdjustments | AddPenStrokes | UpdatePenStrokes | RemovePenStrokes | ErasePenStrokes | SetStrokeCache | ErasePixels | AdoptImage | SetImageDiscarded | AddAnnotation | UpdateAnnotation | RecordAnnotationJob | SetWorkPlan | SetEpisodeOutline | AddMaterialEntry | UpdateMaterialEntry | DecideMaterialProposal | ReplaceText | ApplyPsdImport | ImportCurrentAppProject | SetTextTranslation | SetTextTranslationRemoved | SetReviewStatus | ReorderPages | AddSpread | UpdateSpread | SetEpisodePlan | CarryOverEpisodePlan | AddForeshadowing | UpdateForeshadowing,
    Field(discriminator="type"),
]

op_adapter: TypeAdapter[Op] = TypeAdapter(Op)
