import platform
import numpy as np
from selfdrive.config import UIParams as UP

METER_WIDTH = 20

_COLOR_CACHE = {}
def find_color(lidar_surface, color):
  if color in _COLOR_CACHE:
    return _COLOR_CACHE[color]
  tcolor = 0
  ret = 255
  for x in lidar_surface.get_palette():
    #print tcolor, x
    if x[0:3] == color:
      ret = tcolor
      break
    tcolor += 1
  _COLOR_CACHE[color] = ret
  return ret

def warp_points(pt_s, warp_matrix):
  # pt_s are the source points, nxm array.
  pt_d = np.dot(warp_matrix[:, :-1], pt_s.T) + warp_matrix[:, -1, None]

  # Divide by last dimension for representation in image space.
  return (pt_d[:-1, :] / pt_d[-1, :]).T

def to_lid_pt(y, x):
  px, py = -x * UP.lidar_zoom + UP.lidar_car_x, -y * UP.lidar_zoom + UP.lidar_car_y
  if px > 0 and py > 0 and px < UP.lidar_x and py < UP.lidar_y:
    return int(px), int(py)
  return -1, -1


def draw_path(y, x, color, img, calibration, top_down, lid_color=None):
  # TODO: Remove big box.
  uv_model_real = warp_points(np.column_stack((x, y)), calibration.car_to_model)
  uv_model = np.round(uv_model_real).astype(int)

  uv_model_dots = uv_model[np.logical_and.reduce((np.all(  # pylint: disable=no-member
    uv_model > 0, axis=1), uv_model[:, 0] < img.shape[1] - 1, uv_model[:, 1] <
                                                  img.shape[0] - 1))]

  for i, j  in ((-1, 0), (0, -1), (0, 0), (0, 1), (1, 0)):
    img[uv_model_dots[:, 1] + i, uv_model_dots[:, 0] + j] = color

  # draw lidar path point on lidar
  # find color in 8 bit
  if lid_color is not None and top_down is not None:
    tcolor = find_color(top_down[0], lid_color)
    for i in xrange(len(x)):
      px, py = to_lid_pt(x[i], y[i])
      if px != -1:
        top_down[1][px, py] = tcolor

def draw_steer_path(speed_ms, curvature, color, img,
                    calibration, top_down, VM, lid_color=None):
  path_x = np.arange(101.)
  path_y =  np.multiply(path_x, np.tan(np.arcsin(np.clip(path_x * curvature, -0.999, 0.999)) / 2.))

  draw_path(path_y, path_x, color, img, calibration, top_down, lid_color)

def draw_lead_car(closest, top_down):
  if closest != None:
    closest_y = int(round(UP.lidar_car_y - closest * UP.lidar_zoom))
    if closest_y > 0:
      top_down[1][int(round(UP.lidar_car_x - METER_WIDTH * 2)):int(
        round(UP.lidar_car_x + METER_WIDTH * 2)), closest_y] = find_color(
          top_down[0], (255, 0, 0))

def draw_lead_on(img, closest_x_m, closest_y_m, img_offset, calibration, color, sz=10):
  uv = warp_points(np.asarray([closest_x_m, closest_y_m]), calibration.car_to_bb)[0]
  u, v = int(uv[0] + img_offset[0]), int(uv[1] + img_offset[1])
  if u > 0 and u < 640 and v > 0 and v < 480 - 5:
    img[v - 5 - sz:v - 5 + sz, u] = color
    img[v - 5, u - sz:u + sz] = color
  return u, v

# for plots
import pygame
import matplotlib

if platform.system() != 'Darwin':
  matplotlib.use('QT4Agg')

import matplotlib.pyplot as plt

def init_plots(arr, name_to_arr_idx, plot_xlims, plot_ylims, plot_names, plot_colors, plot_styles, bigplots=False):
  color_palette = { "r": (1,0,0),
                    "g": (0,1,0),
                    "b": (0,0,1),
                    "k": (0,0,0),
                    "y": (1,1,0),
                    "p": (0,1,1),
                    "m": (1,0,1) }

  if bigplots == True:
    fig = plt.figure(figsize=(6.4, 7.0))
  elif bigplots == False:
    fig = plt.figure()
  else:
    fig = plt.figure(figsize=bigplots)

  fig.set_facecolor((0.2,0.2,0.2))

  axs = []
  for pn in range(len(plot_ylims)):
    ax = fig.add_subplot(len(plot_ylims),1,len(axs)+1)
    ax.set_xlim(plot_xlims[pn][0], plot_xlims[pn][1])
    ax.set_ylim(plot_ylims[pn][0], plot_ylims[pn][1])
    ax.patch.set_facecolor((0.4, 0.4, 0.4))
    axs.append(ax)

  plots = [] ;idxs = [] ;plot_select = []
  for i, pl_list in enumerate(plot_names):
    for j, item in enumerate(pl_list):
      plot, = axs[i].plot(arr[:, name_to_arr_idx[item]],
                          label=item,
                          color=color_palette[plot_colors[i][j]],
                          linestyle=plot_styles[i][j])
      plots.append(plot)
      idxs.append(name_to_arr_idx[item])
      plot_select.append(i)
    axs[i].set_title(", ".join("%s (%s)" % (nm, cl)
                               for (nm, cl) in zip(pl_list, plot_colors[i])), fontsize=10)
    if i < len(plot_ylims) - 1:
      axs[i].set_xticks([])

  fig.canvas.draw()

  renderer = fig.canvas.get_renderer()

  if matplotlib.get_backend() == "MacOSX":
    fig.draw(renderer)

  def draw_plots(arr):
    for ax in axs:
      ax.draw_artist(ax.patch)
    for i in range(len(plots)):
      plots[i].set_ydata(arr[:, idxs[i]])
      axs[plot_select[i]].draw_artist(plots[i])

    if matplotlib.get_backend() == "QT4Agg":
      fig.canvas.update()
      fig.canvas.flush_events()

    raw_data = renderer.tostring_rgb()
    #print fig.canvas.get_width_height()
    plot_surface = pygame.image.frombuffer(raw_data, fig.canvas.get_width_height(), "RGB").convert()
    return plot_surface

  return draw_plots


def draw_mpc(liveMpc, top_down):
  mpc_color = find_color(top_down[0], (0, 255, 0))
  for p in zip(liveMpc.liveMpc.x, liveMpc.liveMpc.y):
    px, py = to_lid_pt(*p)
    top_down[1][px, py] = mpc_color
