from void_terminal.toolbox import trimmed_format_exc, ProxyNetworkActivate
from autogen.gradio_gui.utils.pipe import PluginMultiprocessManager, PipeCom
import time


class AutoGenGeneral(PluginMultiprocessManager):

    def gpt_academic_print_override(self, user_proxy, message, sender):
        # ⭐⭐ run in subprocess
        self.child_conn.send(PipeCom("show", sender.name + '\n\n---\n\n' + message['content']))

    def gpt_academic_get_human_input(self, user_proxy, message):
        # ⭐⭐ run in subprocess
        patience = 300
        begin_waiting_time = time.time()
        self.child_conn.send(PipeCom("interact", message))
        while True:
            time.sleep(0.5)
            if self.child_conn.poll(): 
                wait_success = True
                break
            if time.time() - begin_waiting_time > patience:
                self.child_conn.send(PipeCom("done", ""))
                wait_success = False
                break
        if wait_success:
            return self.child_conn.recv().content
        else:
            raise TimeoutError("waiting user input timeout")

    def define_agents(self):
        raise NotImplementedError

    def do_audogen(self, input):
        # ⭐⭐ run in subprocess
        input = input.content
        with ProxyNetworkActivate("AutoGen"):
            code_execution_config={"work_dir": self.autogen_work_dir, "use_docker":self.use_docker}
            agents = self.define_agents()
            user_proxy = None
            assistant = None
            for agent_kwargs in agents:
                agent_cls = agent_kwargs.pop('cls')
                kwargs = {
                    'code_execution_config':code_execution_config
                }
                kwargs.update(agent_kwargs)
                agent_handle = agent_cls(**kwargs)
                agent_handle._print_received_message = lambda a,b: self.gpt_academic_print_override(agent_kwargs, a, b)
                if agent_kwargs['name'] == 'user_proxy':
                    agent_handle.get_human_input = lambda a: self.gpt_academic_get_human_input(user_proxy, a)
                    user_proxy = agent_handle
                if agent_kwargs['name'] == 'assistant': assistant = agent_handle
            try:
                if user_proxy is None or assistant is None: raise Exception("user_proxy or assistant is not defined")
                user_proxy.initiate_chat(assistant, message=input)
            except Exception as e:
                tb_str = '```\n' + trimmed_format_exc() + '```'
                self.child_conn.send(PipeCom("done", "AutoGen exe failed: \n\n" + tb_str))

    def subprocess_worker(self, child_conn):
        # ⭐⭐ run in subprocess
        self.child_conn = child_conn
        while True:
            msg = self.child_conn.recv() # PipeCom
            self.do_audogen(msg)



class AutoGenGroupChat(AutoGenGeneral):

    def do_audogen(self, input):
        # ⭐⭐ run in subprocess
        import autogen
        from void_terminal.toolbox import trimmed_format_exc, ProxyNetworkActivate
        from autogen.gradio_gui.utils.pipe import PipeCom
        input = input.content
        with ProxyNetworkActivate("AutoGen"):
            code_execution_config={"work_dir": self.autogen_work_dir, "use_docker":self.use_docker}
            agents = self.define_agents()
            agents_instances = []
            for agent_kwargs in agents:
                agent_cls = agent_kwargs.pop('cls')
                kwargs = {
                    'code_execution_config':code_execution_config
                }
                kwargs.update(agent_kwargs)
                agent_handle = agent_cls(**kwargs)
                agent_handle._print_received_message = lambda a,b: self.gpt_academic_print_override(agent_kwargs, a, b)
                agents_instances.append(agent_handle)
                if agent_kwargs['name'] == 'user_proxy':
                    user_proxy = agent_handle
                    user_proxy.get_human_input = lambda a: self.gpt_academic_get_human_input(user_proxy, a)
            try:
                groupchat = autogen.GroupChat(agents=agents_instances, messages=[], max_round=50)
                manager = autogen.GroupChatManager(groupchat=groupchat, **self.define_group_chat_manager_config())
                manager._print_received_message = lambda a,b: self.gpt_academic_print_override(agent_kwargs, a, b)
                manager.get_human_input = lambda a: self.gpt_academic_get_human_input(manager, a)
                if user_proxy is None: raise Exception("user_proxy is not defined")
                user_proxy.initiate_chat(manager, message=input)
            except Exception as e:
                tb_str = '```\n' + trimmed_format_exc() + '```'
                self.child_conn.send(PipeCom("done", "AutoGen exe failed: \n\n" + tb_str))

    def define_group_chat_manager_config(self):
        raise NotImplementedError