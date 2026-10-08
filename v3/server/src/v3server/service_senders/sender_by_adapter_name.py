"""つなぎ先の adapter の名前から、送り手を引く表。"""


from v3server.service_senders.comfyui_sender import call_comfyui
from v3server.service_senders.detector_sender import call_detector
from v3server.service_senders.litellm_sender import call_litellm
from v3server.service_senders.sender_result_types import Adapter

ADAPTERS: dict[str, Adapter] = {"litellm": call_litellm, "comfyui": call_comfyui, "detector": call_detector}
