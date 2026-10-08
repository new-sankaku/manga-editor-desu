"""background_scene3d の試験。箱1つ・床と壁の小さな場所で、奥行きと線を確かめる。"""
import numpy as np
import pytest

from v3server.background_scene3d.box_scene_depth_render import Box, Camera, LineSettings, camera_rays, render_depth_and_line

LINE = LineSettings(depth_jump_log=0.05, thickness_px=2)


def test_rays_directions():
    d = camera_rays(3, 3, Camera((0, 0, 0), 0, 0, 90))
    assert np.allclose(d[1, 1], [0, 0, 1])
    assert d[0, 1, 1] > 0  # 上の行は上を向く
    assert d[1, 2, 0] > 0  # 右の列は右を向く
    right = camera_rays(1, 1, Camera((0, 0, 0), 90, 0, 60))
    assert np.allclose(right[0, 0], [1, 0, 0])  # 水平の角度が正なら右（+x）
    down = camera_rays(1, 1, Camera((0, 0, 0), 0, 30, 60))
    assert down[0, 0, 1] < 0  # 上下の角度が正なら下を向く


def test_box_in_front_depth_and_outline():
    # 真ん前に箱が1つ、ほかは何も無い
    box = Box(-1, -1, 5, 1, 1, 6)
    r = render_depth_and_line([box], Camera((0, 0, 0), 0, 0, 90), 64, 64, LINE)
    depth = np.asarray(r.depth)[:, :, 0]
    line = np.asarray(r.line)[:, :, 0]
    assert r.depth.size == (64, 64) and r.depth.mode == 'RGB'
    assert depth[32, 32] > 0  # 箱の所は白寄り
    assert depth[2, 2] == 0  # 何も無い所は黒
    assert line[32, 32] == 255 and line[2, 2] == 255  # 面の中と何も無い所に線は無い
    # 箱の縁（左右の真ん中の行で、箱の端）に線がある
    row = line[32]
    assert (row == 0).sum() >= 2
    xs = np.nonzero(row == 0)[0]
    assert xs.min() < 32 < xs.max()


def test_nearer_is_whiter():
    near = Box(-3, -1, 3, -1, 1, 3.5)
    far = Box(1, -1, 10, 3, 1, 10.5)
    r = render_depth_and_line([near, far], Camera((0, 0, 0), 0, 0, 90), 64, 32, LINE)
    depth = np.asarray(r.depth)[:, :, 0]
    assert depth[16, 10] > depth[16, 54] >= 0


def test_inside_room_sees_walls():
    # 部屋の中から：床・天井・壁で囲まれているので全部の画素が当たる
    room = [Box(-4, -0.1, -1, 4, 0, 10), Box(-4, 3, -1, 4, 3.1, 10), Box(-4.1, 0, -1, -4, 3, 10),
            Box(4, 0, -1, 4.1, 3, 10), Box(-4, 0, 10, 4, 3, 10.1), Box(-4, 0, -1.1, 4, 3, -1)]
    r = render_depth_and_line(room, Camera((0, 1.5, 0.2), 0, 0, 70), 48, 32, LINE)
    depth = np.asarray(r.depth)[:, :, 0]
    assert (depth > 0).mean() > 0.9
    assert (np.asarray(r.line)[:, :, 0] == 0).any()  # 壁と床の境目に線


def test_thickness_does_not_wrap():
    box = Box(-1, -1, 5, 1, 1, 6)
    r = render_depth_and_line([box], Camera((0, 0, 0), 0, 0, 90), 64, 64, LineSettings(0.05, 3))
    line = np.asarray(r.line)[:, :, 0]
    assert (line[0, :] == 255).all() and (line[:, 0] == 255).all()


def test_errors():
    cam = Camera((0, 0, 0), 0, 0, 90)
    with pytest.raises(ValueError):
        render_depth_and_line([], cam, 8, 8, LINE)
    with pytest.raises(ValueError):
        render_depth_and_line([Box(-1, -1, -6, 1, 1, -5)], cam, 8, 8, LINE)  # 後ろの箱は見えない
    with pytest.raises(ValueError):
        render_depth_and_line([Box(-1, -1, 5, 1, 1, 6)], cam, 8, 8, LineSettings(0.05, 0))
