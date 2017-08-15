
bl_info = {
    'name': 'Rename meta to content',
    'author': 'Sybren A. Stüvel',
    'version': (1, 0),
    'blender': (2, 77, 0),
    'location': 'Video Sequence Editor',
    'category': 'Sequencer',
}

import bpy


class SEQUENCER_OT_setup_meta(bpy.types.Operator):
    bl_idname = 'sequencer.setup_meta'
    bl_label = 'Set up meta strip'
    bl_description = 'Renames the selected meta strip to the video strip it contains, and sets up proxies'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(s.type == 'META' for s in context.selected_sequences)

    def execute(self, context):

        meta_strips = (s for s in context.selected_sequences
                       if s.type == 'META')

        for strip in meta_strips:
            strip.use_proxy = False

            candidates = []
            for sub in strip.sequences:
                if sub.type == 'MOVIE':
                    candidates.insert(0, bpy.path.basename(sub.filepath))
                    sub.use_proxy = True
                    sub.proxy.build_25 = False
                    sub.proxy.build_50 = True
                    sub.proxy.quality = 80
                else:
                    candidates.append(sub.name)

            if candidates:
                strip.name = candidates[0]

        return {'FINISHED'}


class SEQUENCER_OT_mute_audio(bpy.types.Operator):
    bl_idname = 'sequencer.mute_audio'
    bl_label = 'Toggle audio in meta strips'
    bl_description = 'Mutes/unmutes the audio inside selected meta strips'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if not context.scene.sequence_editor:
            return False
        return any(s.type == 'META' for s in context.selected_sequences)

    def execute(self, context):
        # Figure out what to do (mute/unmute)
        se = context.scene.sequence_editor
        act_strip = se.active_strip
        mute = True
        for sub in act_strip.sequences:
            if sub.type != 'SOUND':
                continue
            mute = not sub.mute
            break

        for strip in context.selected_sequences:
            if strip.type != 'META':
                continue

            for sub in strip.sequences:
                if sub.type != 'SOUND':
                    continue
                sub.mute = mute

        return {'FINISHED'}


class SEQUENCER_OT_unmeta(bpy.types.Operator):
    bl_idname = 'sequencer.unmeta'
    bl_label = 'Crop contents'
    bl_description = 'Crops contents to start/end of meta strip'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if not context.scene.sequence_editor:
            return False
        return any(s.type == 'META' for s in context.selected_sequences)

    def execute(self, context):
        for strip in context.selected_sequences:
            if strip.type != 'META':
                continue

            for sub in strip.sequences:
                sub.frame_start = strip.frame_start
                sub.frame_offset_start = strip.frame_offset_start
                sub.frame_offset_end = strip.frame_offset_end

        return {'FINISHED'}


class SEQUENCER_OT_select_here(bpy.types.Operator):
    bl_idname = 'sequencer.select_here'
    bl_label = 'Select strips at current frame'
    bl_description = 'Selects only those strips that overlap with the current frame'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.scene.sequence_editor and context.scene.sequence_editor.sequences

    def execute(self, context):
        fra = context.scene.frame_current

        for strip in context.scene.sequence_editor.sequences:
            strip.select = strip.frame_final_start <= fra < strip.frame_final_end
            strip.select_left_handle = strip.select
            strip.select_right_handle = False

        return {'FINISHED'}


def render_header(self, context):
        layout = self.layout
        layout.operator(SEQUENCER_OT_setup_meta.bl_idname)
        layout.operator(SEQUENCER_OT_mute_audio.bl_idname)
        layout.operator(SEQUENCER_OT_unmeta.bl_idname)


def render_select_menu(self, context):
    layout = self.layout
    layout.operator(SEQUENCER_OT_select_here.bl_idname)


def register():
    bpy.utils.register_class(SEQUENCER_OT_setup_meta)
    bpy.utils.register_class(SEQUENCER_OT_mute_audio)
    bpy.utils.register_class(SEQUENCER_OT_unmeta)
    bpy.utils.register_class(SEQUENCER_OT_select_here)
    bpy.types.SEQUENCER_HT_header.append(render_header)
    bpy.types.SEQUENCER_MT_select.append(render_select_menu)


def unregister():
    bpy.utils.unregister_class(SEQUENCER_OT_setup_meta)
    bpy.utils.unregister_class(SEQUENCER_OT_mute_audio)
    bpy.utils.unregister_class(SEQUENCER_OT_unmeta)
    bpy.utils.unregister_class(SEQUENCER_OT_select_here)
    bpy.types.SEQUENCER_HT_header.remove(render_header)
